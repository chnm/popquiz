import json

from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, TemplateView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse
from django.db.models import Count, Q, Case, When, IntegerField, Value

from accounts.models import User
from .models import Category, Item
from .forms import AddItemForm
from .imdb_utils import fetch_movie_data, search_directors_by_name, fetch_director_filmography
from votes.models import Vote


class HomeView(ListView):
    model = Category
    template_name = 'catalog/home.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return Category.objects.annotate(item_count=Count('items'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Order users: those with last names first (alphabetically), then by username
        # This handles users who sign up without providing first_name/last_name
        context['users'] = User.objects.filter(is_staff=False).annotate(
            has_last_name=Case(
                When(last_name='', then=Value(0)),
                default=Value(1),
                output_field=IntegerField()
            )
        ).order_by('-has_last_name', 'last_name', 'first_name', 'username')

        # Get voting progress for logged-in user
        if self.request.user.is_authenticated:
            categories_with_progress = []
            for category in context['categories']:
                total_items = category.item_count
                # Count all votes (including NO_ANSWER) - any response counts as "handled"
                responded_count = Vote.objects.filter(
                    user=self.request.user,
                    item__category=category
                ).count()
                remaining = total_items - responded_count
                progress_percent = round((responded_count / total_items) * 100) if total_items > 0 else 0

                # Get random movie posters for this category
                random_posters = Item.objects.filter(
                    category=category
                ).exclude(
                    poster_url=''
                ).order_by('?')[:5]

                categories_with_progress.append({
                    'category': category,
                    'total': total_items,
                    'voted': responded_count,
                    'remaining': remaining,
                    'progress_percent': progress_percent,
                    'random_posters': random_posters,
                })
            context['categories_with_progress'] = categories_with_progress
        else:
            # For logged-out users, add random posters to categories
            categories_with_posters = []
            for category in context['categories']:
                random_posters = Item.objects.filter(
                    category=category
                ).exclude(
                    poster_url=''
                ).order_by('?')[:5]
                categories_with_posters.append({
                    'category': category,
                    'random_posters': random_posters,
                })
            context['categories_with_posters'] = categories_with_posters

        # Get a random featured movie with vote statistics
        featured_movie = Item.objects.exclude(
            poster_url=''
        ).annotate(
            yes_count=Count('votes', filter=Q(votes__choice=Vote.Choice.YES)),
            no_count=Count('votes', filter=Q(votes__choice=Vote.Choice.NO)),
            meh_count=Count('votes', filter=Q(votes__choice=Vote.Choice.MEH)),
            total_votes=Count('votes', filter=~Q(votes__choice=Vote.Choice.NO_ANSWER))
        ).filter(
            total_votes__gt=0  # Only show movies with at least one vote
        ).order_by('?').first()

        if featured_movie:
            # Calculate percentages
            total = featured_movie.total_votes
            if total > 0:
                featured_movie.yes_percent = round((featured_movie.yes_count / total) * 100)
                featured_movie.no_percent = round((featured_movie.no_count / total) * 100)
                featured_movie.meh_percent = round((featured_movie.meh_count / total) * 100)
            else:
                featured_movie.yes_percent = 0
                featured_movie.no_percent = 0
                featured_movie.meh_percent = 0

        context['featured_movie'] = featured_movie

        # Get recent activity (votes and movie additions) for logged-in users
        if self.request.user.is_authenticated:
            activities = []

            # Get recent votes (last 20)
            recent_votes = Vote.objects.exclude(
                choice=Vote.Choice.NO_ANSWER
            ).select_related(
                'user', 'item', 'item__category'
            ).order_by('-updated_at')[:20]

            for vote in recent_votes:
                activities.append({
                    'type': 'vote',
                    'user': vote.user,
                    'item': vote.item,
                    'choice': vote.choice,
                    'timestamp': vote.updated_at,
                })

            # Get recently added movies (last 20)
            # Include all movies, even those added by scripts (added_by=None)
            recent_additions = Item.objects.select_related(
                'added_by', 'category'
            ).order_by('-created_at')[:20]

            for item in recent_additions:
                activities.append({
                    'type': 'addition',
                    'user': item.added_by,  # Will be None for script-added movies
                    'item': item,
                    'timestamp': item.created_at,
                })

            # Sort all activities by timestamp (most recent first)
            activities.sort(key=lambda x: x['timestamp'], reverse=True)

            # Limit to 15 most recent activities
            context['recent_activities'] = activities[:15]

        return context


class CategoryDetailView(DetailView):
    model = Category
    template_name = 'catalog/category_detail.html'
    context_object_name = 'category'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        items = self.object.items.all()

        if self.request.user.is_authenticated:
            user_votes = Vote.objects.filter(
                user=self.request.user,
                item__in=items
            ).select_related('item')
            votes_dict = {vote.item_id: vote.choice for vote in user_votes}
        else:
            votes_dict = {}

        items_with_votes = []
        for item in items:
            items_with_votes.append({
                'item': item,
                'vote': votes_dict.get(item.id, Vote.Choice.NO_ANSWER)
            })

        # Sort items by vote preference: Yes, Meh, No, Not Seen
        vote_order = {
            Vote.Choice.YES: 0,
            Vote.Choice.MEH: 1,
            Vote.Choice.NO: 2,
            Vote.Choice.NO_ANSWER: 3,
        }
        items_with_votes.sort(key=lambda x: (vote_order.get(x['vote'], 3), x['item'].title.lower()))

        context['items_with_votes'] = items_with_votes
        return context


class AddItemView(LoginRequiredMixin, View):
    """View to add a movie using just an IMDB URL."""

    def get(self, request, slug):
        category = get_object_or_404(Category, slug=slug)
        form = AddItemForm()
        return render(request, 'catalog/add_item.html', {
            'form': form,
            'category': category,
        })

    def post(self, request, slug):
        category = get_object_or_404(Category, slug=slug)
        form = AddItemForm(request.POST)

        if form.is_valid():
            imdb_url = form.cleaned_data['imdb_url']

            # Fetch movie data from IMDB
            movie_data = fetch_movie_data(imdb_url)

            if not movie_data:
                form.add_error('imdb_url', 'Could not fetch movie data from IMDB. Please check the URL and try again.')
                return render(request, 'catalog/add_item.html', {
                    'form': form,
                    'category': category,
                })

            # Check if movie already exists
            existing = Item.objects.filter(imdb_id=movie_data['imdb_id']).first()
            if existing:
                form.add_error('imdb_url', f'This movie already exists: "{existing.title}"')
                return render(request, 'catalog/add_item.html', {
                    'form': form,
                    'category': category,
                })

            # Create the item
            item = Item.objects.create(
                category=category,
                title=movie_data['title'],
                year=movie_data['year'],
                director=movie_data.get('director') or '',
                genre=movie_data.get('genre') or '',
                imdb_id=movie_data['imdb_id'],
                imdb_url=movie_data['imdb_url'],
                poster_url=movie_data['poster_url'] or '',
                added_by=request.user,
            )

            messages.success(request, f'"{item.title}" has been added!')
            return redirect('category_detail', slug=slug)

        return render(request, 'catalog/add_item.html', {
            'form': form,
            'category': category,
        })


class AddByDirectorView(LoginRequiredMixin, View):
    """View to add all movies by a director automatically by searching IMDB by name."""

    def get(self, request, slug):
        category = get_object_or_404(Category, slug=slug)
        return render(request, 'catalog/add_by_director.html', {
            'category': category,
        })

    def post(self, request, slug):
        category = get_object_or_404(Category, slug=slug)

        # Check if user is selecting from search results
        if 'director_id' in request.POST:
            return self._add_movies_by_director_id(request, category, slug)

        # Otherwise, search for director by name
        director_name = request.POST.get('director_name', '').strip()

        if not director_name:
            messages.error(request, 'Please enter a director name.')
            return render(request, 'catalog/add_by_director.html', {
                'category': category,
            })

        # Search IMDB for directors matching this name
        search_results = search_directors_by_name(director_name)

        if not search_results:
            messages.error(request, f'No directors found matching "{director_name}". Please check the spelling and try again.')
            return render(request, 'catalog/add_by_director.html', {
                'category': category,
                'director_name': director_name,
            })

        # If exactly one result, proceed automatically
        if len(search_results) == 1:
            director_id = search_results[0]['imdb_id']
            return self._add_movies_by_director_id(request, category, slug, director_id)

        # Multiple results - show selection page
        return render(request, 'catalog/add_by_director.html', {
            'category': category,
            'director_name': director_name,
            'search_results': search_results,
        })

    def _add_movies_by_director_id(self, request, category, slug, director_id=None):
        """Helper method to add movies once director is determined."""
        if director_id is None:
            director_id = request.POST.get('director_id', '').strip()

        if not director_id:
            messages.error(request, 'No director selected.')
            return redirect('add_by_director', slug=slug)

        # Fetch filmography using the director's IMDB ID
        filmography = fetch_director_filmography(director_id)

        if not filmography:
            messages.error(request, 'Could not fetch director filmography. Please try again.')
            return redirect('add_by_director', slug=slug)

        director_name = filmography['name']
        movies = filmography['movies']

        if not movies:
            messages.warning(request, f'No movies found for {director_name}.')
            return redirect('add_by_director', slug=slug)

        # Automatically add all movies that don't already exist
        added_count = 0
        skipped_count = 0
        failed_count = 0

        for movie in movies:
            imdb_id = movie['imdb_id']

            # Check if already exists
            if Item.objects.filter(imdb_id=imdb_id).exists():
                skipped_count += 1
                continue

            # Fetch full movie data
            movie_data = fetch_movie_data(imdb_id)

            if not movie_data:
                failed_count += 1
                continue

            # Double-check: Filter out TV shows and other non-movies that slipped through
            # IMDB sometimes doesn't include type info in aria-labels on director pages
            title = movie_data['title']
            is_not_movie = (
                'TV Series' in title or
                'TV Mini-Series' in title or
                'TV Movie' in title or
                'TV Episode' in title or
                'TV Special' in title or
                'Music Video' in title or
                'Video Game' in title or
                'Short' in title or
                '(Short' in title
            )
            if is_not_movie:
                skipped_count += 1
                continue

            # CRITICAL: Verify this person was actually the director of this movie
            # Many people (like John Hughes) wrote/produced movies they didn't direct
            movie_director = movie_data.get('director') or ''
            if movie_director and director_name not in movie_director:
                # Director name doesn't match - this person was NOT the director
                # They might have been the writer or producer
                skipped_count += 1
                continue

            # Create the item
            Item.objects.create(
                category=category,
                title=movie_data['title'],
                year=movie_data['year'],
                director=movie_data.get('director') or '',
                genre=movie_data.get('genre') or '',
                imdb_id=movie_data['imdb_id'],
                imdb_url=movie_data['imdb_url'],
                poster_url=movie_data['poster_url'] or '',
                added_by=request.user,
            )
            added_count += 1

        # Show completion message
        if added_count > 0:
            messages.success(request, f'Done, I have added {added_count} {director_name} movie{"s" if added_count != 1 else ""} to {category.name}!')
        elif skipped_count > 0 and failed_count == 0:
            messages.info(request, f'All {skipped_count} {director_name} movies are already in your {category.name} collection.')
        elif failed_count > 0 and added_count == 0:
            messages.warning(request, f'Could not add {director_name} movies. {failed_count} movie{"s" if failed_count != 1 else ""} failed to fetch from IMDB.')
        else:
            message_parts = []
            if added_count > 0:
                message_parts.append(f'added {added_count}')
            if skipped_count > 0:
                message_parts.append(f'skipped {skipped_count} (already in database)')
            if failed_count > 0:
                message_parts.append(f'{failed_count} failed')
            messages.info(request, f'{director_name}: {", ".join(message_parts)}')

        return redirect('category_detail', slug=slug)


class SwipeVoteView(LoginRequiredMixin, TemplateView):
    template_name = 'catalog/swipe_vote.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = get_object_or_404(Category, slug=self.kwargs['slug'])
        context['category'] = category

        # Get items user has already voted on
        voted_item_ids = Vote.objects.filter(
            user=self.request.user,
            item__category=category
        ).values_list('item_id', flat=True)

        # Get unvoted items, ordered by total vote count (most popular first)
        unvoted_items = Item.objects.filter(
            category=category
        ).exclude(
            id__in=voted_item_ids
        ).annotate(
            vote_count=Count('votes')
        ).order_by('-vote_count', 'title')

        context['current_item'] = unvoted_items.first()
        context['remaining_count'] = unvoted_items.count()
        context['total_count'] = Item.objects.filter(category=category).count()
        context['voted_count'] = context['total_count'] - context['remaining_count']

        return context


class StatsView(TemplateView):
    """View showing movies ranked by team preference."""
    template_name = 'catalog/stats.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = get_object_or_404(Category, slug=self.kwargs['slug'])
        context['category'] = category

        # Count team members (non-staff users)
        team_count = User.objects.filter(is_staff=False).count()
        context['team_count'] = team_count

        # Get all items with vote statistics (only yes/no/meh, not "haven't watched")
        items = Item.objects.filter(category=category).annotate(
            yes_count=Count('votes', filter=Q(votes__choice=Vote.Choice.YES)),
            no_count=Count('votes', filter=Q(votes__choice=Vote.Choice.NO)),
            meh_count=Count('votes', filter=Q(votes__choice=Vote.Choice.MEH)),
        )

        # Calculate global average score first (for Bayesian average)
        # We'll use this to stabilize scores for movies with few votes
        total_yes = 0
        total_no = 0
        total_meh = 0
        for item in items:
            total_yes += item.yes_count
            total_no += item.no_count
            total_meh += item.meh_count

        total_all_votes = total_yes + total_no + total_meh
        if total_all_votes > 0:
            global_average = ((total_yes - total_no) / total_all_votes) * 100
        else:
            global_average = 0

        # Confidence parameter: number of votes needed to trust the movie's own score
        # Higher value = more conservative (pulls toward global average more)
        # Lower value = less conservative (trusts individual scores more)
        C = 5  # Equivalent to "5 average votes" worth of confidence

        # Calculate scores for all movies
        ranked_movies = []

        for item in items:
            # Total votes = only those who actually watched (yes + no + meh)
            total_votes = item.yes_count + item.no_count + item.meh_count
            if total_votes > 0:
                # Raw score from -100 to +100
                raw_score = ((item.yes_count - item.no_count) / total_votes) * 100

                # Bayesian average: blend raw score with global average
                # Formula: (C * global_avg + total_votes * raw_score) / (C + total_votes)
                # This way:
                # - Movies with few votes are pulled toward the global average
                # - Movies with many votes use mostly their own score
                bayesian_score = (C * global_average + total_votes * raw_score) / (C + total_votes)
                score = round(bayesian_score)

                yes_percent = round((item.yes_count / total_votes) * 100)
                no_percent = round((item.no_count / total_votes) * 100)
                meh_percent = round((item.meh_count / total_votes) * 100)
            else:
                score = None  # No votes yet
                yes_percent = 0
                no_percent = 0
                meh_percent = 0

            ranked_movies.append({
                'item': item,
                'yes_count': item.yes_count,
                'no_count': item.no_count,
                'meh_count': item.meh_count,
                'total_votes': total_votes,
                'score': score,
                'yes_percent': yes_percent,
                'no_percent': no_percent,
                'meh_percent': meh_percent,
            })

        # Sort: movies with votes first (by score desc), then unvoted movies by title
        ranked_movies.sort(key=lambda x: (
            x['score'] is None,  # Unvoted movies go last
            -(x['score'] or 0),  # Higher scores first
            -x['yes_count'],     # More yes votes as tiebreaker
            x['item'].title.lower()
        ))

        context['ranked_movies'] = ranked_movies

        return context


class DecadeStatsView(TemplateView):
    """View showing movies ranked by decade."""
    template_name = 'catalog/decades.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = get_object_or_404(Category, slug=self.kwargs['slug'])
        context['category'] = category

        # Get all items with vote statistics
        items = Item.objects.filter(category=category).annotate(
            yes_count=Count('votes', filter=Q(votes__choice=Vote.Choice.YES)),
            no_count=Count('votes', filter=Q(votes__choice=Vote.Choice.NO)),
            meh_count=Count('votes', filter=Q(votes__choice=Vote.Choice.MEH)),
        )

        # Calculate global average for Bayesian scoring
        total_yes = 0
        total_no = 0
        total_meh = 0
        for item in items:
            total_yes += item.yes_count
            total_no += item.no_count
            total_meh += item.meh_count

        total_all_votes = total_yes + total_no + total_meh
        if total_all_votes > 0:
            global_average = ((total_yes - total_no) / total_all_votes) * 100
        else:
            global_average = 0

        C = 5  # Confidence parameter

        # Group movies by decade
        decades = {}
        no_year = []

        for item in items:
            total_votes = item.yes_count + item.no_count + item.meh_count
            if total_votes > 0:
                # Use Bayesian average scoring
                raw_score = ((item.yes_count - item.no_count) / total_votes) * 100
                bayesian_score = (C * global_average + total_votes * raw_score) / (C + total_votes)
                score = round(bayesian_score)

                yes_percent = round((item.yes_count / total_votes) * 100)
                no_percent = round((item.no_count / total_votes) * 100)
                meh_percent = round((item.meh_count / total_votes) * 100)
            else:
                score = None
                yes_percent = 0
                no_percent = 0
                meh_percent = 0

            movie_data = {
                'item': item,
                'yes_count': item.yes_count,
                'no_count': item.no_count,
                'meh_count': item.meh_count,
                'total_votes': total_votes,
                'score': score,
                'yes_percent': yes_percent,
                'no_percent': no_percent,
                'meh_percent': meh_percent,
            }

            if item.year:
                decade = (item.year // 10) * 10
                if decade not in decades:
                    decades[decade] = []
                decades[decade].append(movie_data)
            else:
                no_year.append(movie_data)

        # Sort movies within each decade by score
        for decade in decades:
            decades[decade].sort(key=lambda x: (
                x['score'] is None,
                -(x['score'] or 0),
                -x['yes_count'],
                x['item'].title.lower()
            ))

        # Sort decades (most recent first)
        sorted_decades = sorted(decades.items(), key=lambda x: -x[0])

        context['decades'] = sorted_decades
        context['no_year'] = no_year

        return context


class EclecticView(TemplateView):
    """View showing team members ranked by how eclectic their taste is."""
    template_name = 'catalog/eclectic.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = get_object_or_404(Category, slug=self.kwargs['slug'])
        context['category'] = category

        # Get all votes for this category (excluding NO_ANSWER)
        all_votes = Vote.objects.filter(
            item__category=category
        ).exclude(
            choice=Vote.Choice.NO_ANSWER
        ).select_related('user', 'item')

        # Build a dict of item_id -> list of votes
        item_votes = {}
        for vote in all_votes:
            if vote.item_id not in item_votes:
                item_votes[vote.item_id] = []
            item_votes[vote.item_id].append(vote)

        # For each item, determine the consensus (majority vote)
        # Consensus is the most common vote among yes/no/meh
        item_consensus = {}
        for item_id, votes in item_votes.items():
            if len(votes) < 2:
                # Need at least 2 votes to have a meaningful consensus
                continue
            vote_counts = {
                Vote.Choice.YES: 0,
                Vote.Choice.NO: 0,
                Vote.Choice.MEH: 0,
            }
            for v in votes:
                if v.choice in vote_counts:
                    vote_counts[v.choice] += 1

            # Find the majority vote
            max_count = max(vote_counts.values())
            consensus_votes = [k for k, v in vote_counts.items() if v == max_count]
            # If there's a tie, there's no clear consensus
            if len(consensus_votes) == 1:
                item_consensus[item_id] = consensus_votes[0]

        # For each user, calculate how often they agree/disagree with consensus
        team_members = User.objects.filter(is_staff=False)
        user_stats = []

        for user in team_members:
            user_votes = [v for v in all_votes if v.user_id == user.id]
            agreements = 0
            disagreements = 0
            contrarian_movies = []  # Movies where user disagreed with consensus

            for vote in user_votes:
                if vote.item_id in item_consensus:
                    consensus = item_consensus[vote.item_id]
                    if vote.choice == consensus:
                        agreements += 1
                    else:
                        disagreements += 1
                        contrarian_movies.append({
                            'item': vote.item,
                            'user_vote': vote.choice,
                            'consensus': consensus,
                        })

            total = agreements + disagreements
            if total >= 3:  # Need at least 3 comparable votes
                eclectic_score = round((disagreements / total) * 100)
                user_stats.append({
                    'user': user,
                    'eclectic_score': eclectic_score,
                    'agreements': agreements,
                    'disagreements': disagreements,
                    'total': total,
                    'contrarian_movies': sorted(
                        contrarian_movies,
                        key=lambda x: x['item'].title.lower()
                    )[:5],  # Top 5 contrarian picks
                })

        # Sort by eclectic score (highest = most eclectic)
        user_stats.sort(key=lambda x: (-x['eclectic_score'], x['user'].last_name))

        context['user_stats'] = user_stats
        context['has_data'] = len(user_stats) > 0

        return context


class DivisiveView(TemplateView):
    """View showing movies with the most disagreement (high yes AND high no votes)."""
    template_name = 'catalog/divisive.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = get_object_or_404(Category, slug=self.kwargs['slug'])
        context['category'] = category

        # Get all items with vote statistics
        items = Item.objects.filter(category=category).annotate(
            yes_count=Count('votes', filter=Q(votes__choice=Vote.Choice.YES)),
            no_count=Count('votes', filter=Q(votes__choice=Vote.Choice.NO)),
            meh_count=Count('votes', filter=Q(votes__choice=Vote.Choice.MEH)),
        )

        # Calculate divisiveness for each movie
        divisive_movies = []

        for item in items:
            total_votes = item.yes_count + item.no_count + item.meh_count

            # Need at least 5 votes to be considered
            if total_votes >= 5:
                # Divisiveness score = min(yes, no) - measures how many are on minority side
                # Higher score = more people on both sides = more divisive
                divisiveness_score = min(item.yes_count, item.no_count)

                # Calculate percentages
                yes_percent = round((item.yes_count / total_votes) * 100) if total_votes > 0 else 0
                no_percent = round((item.no_count / total_votes) * 100) if total_votes > 0 else 0
                meh_percent = round((item.meh_count / total_votes) * 100) if total_votes > 0 else 0

                divisive_movies.append({
                    'item': item,
                    'yes_count': item.yes_count,
                    'no_count': item.no_count,
                    'meh_count': item.meh_count,
                    'total_votes': total_votes,
                    'divisiveness_score': divisiveness_score,
                    'yes_percent': yes_percent,
                    'no_percent': no_percent,
                    'meh_percent': meh_percent,
                })

        # Sort by divisiveness score (highest first)
        divisive_movies.sort(key=lambda x: (
            -x['divisiveness_score'],  # Most divisive first
            -x['total_votes'],         # More votes as tiebreaker
            x['item'].title.lower()
        ))

        context['divisive_movies'] = divisive_movies
        context['has_data'] = len(divisive_movies) > 0

        return context


class MovieDetailView(TemplateView):
    """View showing how everyone voted on a specific movie."""
    template_name = 'catalog/movie_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = get_object_or_404(Category, slug=self.kwargs['category_slug'])
        item = get_object_or_404(Item, id=self.kwargs['item_id'], category=category)

        context['category'] = category
        context['item'] = item

        # Get all votes for this item, grouped by choice
        all_votes = Vote.objects.filter(item=item).select_related('user').order_by('user__last_name', 'user__first_name')

        # Group votes by choice
        yes_votes = []
        no_votes = []
        meh_votes = []
        not_seen_votes = []

        for vote in all_votes:
            if vote.choice == Vote.Choice.YES:
                yes_votes.append(vote)
            elif vote.choice == Vote.Choice.NO:
                no_votes.append(vote)
            elif vote.choice == Vote.Choice.MEH:
                meh_votes.append(vote)
            elif vote.choice == Vote.Choice.NO_ANSWER:
                not_seen_votes.append(vote)

        # Get all team members who haven't voted
        team_members = User.objects.filter(is_staff=False)
        voted_user_ids = set(vote.user_id for vote in all_votes)
        no_vote_users = [user for user in team_members if user.id not in voted_user_ids]
        no_vote_users.sort(key=lambda x: (x.last_name, x.first_name))

        context['yes_votes'] = yes_votes
        context['no_votes'] = no_votes
        context['meh_votes'] = meh_votes
        context['not_seen_votes'] = not_seen_votes
        context['no_vote_users'] = no_vote_users

        # Calculate statistics
        total_votes = len(yes_votes) + len(no_votes) + len(meh_votes)
        context['total_votes'] = total_votes
        context['yes_count'] = len(yes_votes)
        context['no_count'] = len(no_votes)
        context['meh_count'] = len(meh_votes)
        context['not_seen_count'] = len(not_seen_votes)
        context['no_vote_count'] = len(no_vote_users)

        if total_votes > 0:
            context['yes_percent'] = round((len(yes_votes) / total_votes) * 100)
            context['no_percent'] = round((len(no_votes) / total_votes) * 100)
            context['meh_percent'] = round((len(meh_votes) / total_votes) * 100)
        else:
            context['yes_percent'] = 0
            context['no_percent'] = 0
            context['meh_percent'] = 0

        return context
