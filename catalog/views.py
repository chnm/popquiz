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
from ratings.models import Rating


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
                # Count all ratings (including NO_RATING) - any response counts as "handled"
                responded_count = Rating.objects.filter(
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

        # Get random featured movies with rating statistics for carousel
        featured_movies_qs = Item.objects.exclude(
            poster_url=''
        ).annotate(
            loved_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.LOVED)),
            liked_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.LIKED)),
            okay_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.OKAY)),
            disliked_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.DISLIKED)),
            hated_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.HATED)),
            total_ratings=Count('ratings', filter=~Q(ratings__rating=Rating.Level.NO_RATING))
        ).filter(
            total_ratings__gt=0  # Only show movies with at least one rating
        ).order_by('?')[:10]

        featured_movies = []
        for movie in featured_movies_qs:
            total = movie.total_ratings
            if total > 0:
                movie.loved_percent = round((movie.loved_count / total) * 100)
                movie.liked_percent = round((movie.liked_count / total) * 100)
                movie.okay_percent = round((movie.okay_count / total) * 100)
                movie.disliked_percent = round((movie.disliked_count / total) * 100)
                movie.hated_percent = round((movie.hated_count / total) * 100)
            else:
                movie.loved_percent = 0
                movie.liked_percent = 0
                movie.okay_percent = 0
                movie.disliked_percent = 0
                movie.hated_percent = 0
            featured_movies.append(movie)

        context['featured_movies'] = featured_movies

        # Get recent activity (ratings and movie additions) for logged-in users
        if self.request.user.is_authenticated:
            activities = []

            # Get recent ratings (last 20)
            recent_ratings = Rating.objects.exclude(
                rating=Rating.Level.NO_RATING
            ).select_related(
                'user', 'item', 'item__category'
            ).order_by('-updated_at')[:20]

            for rating in recent_ratings:
                activities.append({
                    'type': 'rating',
                    'user': rating.user,
                    'item': rating.item,
                    'rating': rating.rating,
                    'timestamp': rating.updated_at,
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
            user_ratings = Rating.objects.filter(
                user=self.request.user,
                item__in=items
            ).select_related('item')
            ratings_dict = {rating.item_id: rating.rating for rating in user_ratings}
        else:
            ratings_dict = {}

        items_with_ratings = []
        for item in items:
            items_with_ratings.append({
                'item': item,
                'rating': ratings_dict.get(item.id, Rating.Level.NO_RATING)
            })

        # Sort items by rating preference: Loved, Liked, Okay, Disliked, Hated, Not Rated
        rating_order = {
            Rating.Level.LOVED: 0,
            Rating.Level.LIKED: 1,
            Rating.Level.OKAY: 2,
            Rating.Level.DISLIKED: 3,
            Rating.Level.HATED: 4,
            Rating.Level.NO_RATING: 5,
        }
        items_with_ratings.sort(key=lambda x: (rating_order.get(x['rating'], 5), x['item'].title.lower()))

        context['items_with_ratings'] = items_with_ratings
        context['item_count'] = items.count()
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
                form.add_error('imdb_url', f'This {category.item_label} already exists: "{existing.title}"')
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
            messages.warning(request, f'No {category.item_label}s found for {director_name}.')
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
            label = category.item_label
            messages.success(request, f'Done, I have added {added_count} {director_name} {label}{"s" if added_count != 1 else ""} to {category.name}!')
        elif skipped_count > 0 and failed_count == 0:
            label = category.item_label
            messages.info(request, f'All {skipped_count} {director_name} {label}s are already in your {category.name} collection.')
        elif failed_count > 0 and added_count == 0:
            label = category.item_label
            messages.warning(request, f'Could not add {director_name} {label}s. {failed_count} {label}{"s" if failed_count != 1 else ""} failed to fetch from IMDB.')
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


class SwipeRatingView(LoginRequiredMixin, TemplateView):
    template_name = 'catalog/swipe_rating.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = get_object_or_404(Category, slug=self.kwargs['slug'])
        context['category'] = category

        # Get items user has already rated
        rated_item_ids = Rating.objects.filter(
            user=self.request.user,
            item__category=category
        ).values_list('item_id', flat=True)

        # Get unrated items in random order
        unrated_items = Item.objects.filter(
            category=category
        ).exclude(
            id__in=rated_item_ids
        ).order_by('?')

        context['current_item'] = unrated_items.first()
        context['remaining_count'] = unrated_items.count()
        context['total_count'] = Item.objects.filter(category=category).count()
        context['rated_count'] = context['total_count'] - context['remaining_count']

        return context


class StatsView(TemplateView):
    """View showing movies ranked by team preference using simple averages."""
    template_name = 'catalog/stats.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = get_object_or_404(Category, slug=self.kwargs['slug'])
        context['category'] = category

        # Count team members (non-staff users)
        team_count = User.objects.filter(is_staff=False).count()
        context['team_count'] = team_count

        # Get all items with rating statistics (5-level system)
        items = Item.objects.filter(category=category).annotate(
            loved_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.LOVED)),
            liked_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.LIKED)),
            okay_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.OKAY)),
            disliked_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.DISLIKED)),
            hated_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.HATED)),
        )

        # First pass: calculate simple averages for all movies to get overall mean
        all_averages = []
        for item in items:
            total_ratings = (item.loved_count + item.liked_count + item.okay_count +
                           item.disliked_count + item.hated_count)
            if total_ratings > 0:
                total_value = (item.loved_count * 2 + item.liked_count * 1 +
                             item.okay_count * 0 + item.disliked_count * -1 +
                             item.hated_count * -2)
                all_averages.append(total_value / total_ratings)

        # Calculate overall mean rating (C in Bayesian formula)
        overall_mean = sum(all_averages) / len(all_averages) if all_averages else 0

        # Minimum votes threshold - movies need this many votes to rely on their own average
        MIN_VOTES = 3

        # Second pass: calculate Bayesian scores
        ranked_movies = []

        for item in items:
            # Total ratings = only those who actually rated (not NO_RATING)
            total_ratings = (item.loved_count + item.liked_count + item.okay_count +
                           item.disliked_count + item.hated_count)

            if total_ratings > 0:
                # Calculate simple average for this movie
                # loved=2, liked=1, okay=0, disliked=-1, hated=-2
                total_value = (item.loved_count * 2 + item.liked_count * 1 +
                             item.okay_count * 0 + item.disliked_count * -1 +
                             item.hated_count * -2)
                average = total_value / total_ratings

                # Apply Bayesian averaging to prevent low-sample movies from dominating
                # bayesian = (v/(v+m)) * R + (m/(v+m)) * C
                # where v = votes, m = min threshold, R = movie avg, C = overall mean
                bayesian_average = ((total_ratings / (total_ratings + MIN_VOTES)) * average +
                                  (MIN_VOTES / (total_ratings + MIN_VOTES)) * overall_mean)

                # Convert to 0-100 scale for display (from -2 to +2 range)
                score = round(((bayesian_average + 2) / 4) * 100)

                # Calculate percentages
                loved_percent = round((item.loved_count / total_ratings) * 100)
                liked_percent = round((item.liked_count / total_ratings) * 100)
                okay_percent = round((item.okay_count / total_ratings) * 100)
                disliked_percent = round((item.disliked_count / total_ratings) * 100)
                hated_percent = round((item.hated_count / total_ratings) * 100)
            else:
                score = None  # No ratings yet
                average = 0
                loved_percent = 0
                liked_percent = 0
                okay_percent = 0
                disliked_percent = 0
                hated_percent = 0

            ranked_movies.append({
                'item': item,
                'loved_count': item.loved_count,
                'liked_count': item.liked_count,
                'okay_count': item.okay_count,
                'disliked_count': item.disliked_count,
                'hated_count': item.hated_count,
                'total_ratings': total_ratings,
                'score': score,
                'average': average if total_ratings > 0 else None,
                'loved_percent': loved_percent,
                'liked_percent': liked_percent,
                'okay_percent': okay_percent,
                'disliked_percent': disliked_percent,
                'hated_percent': hated_percent,
            })

        # Sort: movies with ratings first (by score desc), then unrated movies by title
        ranked_movies.sort(key=lambda x: (
            x['score'] is None,  # Unrated movies go last
            -(x['score'] or 0),  # Higher scores first
            -x['loved_count'],   # More loved ratings as tiebreaker
            x['item'].title.lower()
        ))

        context['ranked_movies'] = ranked_movies

        return context


class DecadeStatsView(TemplateView):
    """View showing movies ranked by decade using simple averages."""
    template_name = 'catalog/decades.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = get_object_or_404(Category, slug=self.kwargs['slug'])
        context['category'] = category

        # Get all items with rating statistics
        items = Item.objects.filter(category=category).annotate(
            loved_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.LOVED)),
            liked_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.LIKED)),
            okay_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.OKAY)),
            disliked_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.DISLIKED)),
            hated_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.HATED)),
        )

        # Group movies by decade
        decades = {}
        no_year = []

        for item in items:
            total_ratings = (item.loved_count + item.liked_count + item.okay_count +
                           item.disliked_count + item.hated_count)

            if total_ratings > 0:
                # Simple average
                total_value = (item.loved_count * 2 + item.liked_count * 1 +
                             item.okay_count * 0 + item.disliked_count * -1 +
                             item.hated_count * -2)
                average = total_value / total_ratings
                score = round(((average + 2) / 4) * 100)

                loved_percent = round((item.loved_count / total_ratings) * 100)
                liked_percent = round((item.liked_count / total_ratings) * 100)
                okay_percent = round((item.okay_count / total_ratings) * 100)
                disliked_percent = round((item.disliked_count / total_ratings) * 100)
                hated_percent = round((item.hated_count / total_ratings) * 100)
            else:
                score = None
                average = 0
                loved_percent = 0
                liked_percent = 0
                okay_percent = 0
                disliked_percent = 0
                hated_percent = 0

            movie_data = {
                'item': item,
                'loved_count': item.loved_count,
                'liked_count': item.liked_count,
                'okay_count': item.okay_count,
                'disliked_count': item.disliked_count,
                'hated_count': item.hated_count,
                'total_ratings': total_ratings,
                'score': score,
                'average': average if total_ratings > 0 else None,
                'loved_percent': loved_percent,
                'liked_percent': liked_percent,
                'okay_percent': okay_percent,
                'disliked_percent': disliked_percent,
                'hated_percent': hated_percent,
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
                -x['loved_count'],
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

        # Get all ratings for this category (excluding NO_RATING)
        all_ratings = Rating.objects.filter(
            item__category=category
        ).exclude(
            rating=Rating.Level.NO_RATING
        ).select_related('user', 'item')

        # Build a dict of item_id -> list of ratings
        item_ratings = {}
        for rating in all_ratings:
            if rating.item_id not in item_ratings:
                item_ratings[rating.item_id] = []
            item_ratings[rating.item_id].append(rating)

        # For each item, determine the consensus (majority rating)
        # Consensus is the most common rating among the 5 levels
        item_consensus = {}
        for item_id, ratings in item_ratings.items():
            if len(ratings) < 2:
                # Need at least 2 ratings to have a meaningful consensus
                continue
            rating_counts = {
                Rating.Level.LOVED: 0,
                Rating.Level.LIKED: 0,
                Rating.Level.OKAY: 0,
                Rating.Level.DISLIKED: 0,
                Rating.Level.HATED: 0,
            }
            for r in ratings:
                if r.rating in rating_counts:
                    rating_counts[r.rating] += 1

            # Find the majority rating
            max_count = max(rating_counts.values())
            consensus_ratings = [k for k, v in rating_counts.items() if v == max_count]
            # If there's a tie, there's no clear consensus
            if len(consensus_ratings) == 1:
                item_consensus[item_id] = consensus_ratings[0]

        # For each user, calculate how often they agree/disagree with consensus
        team_members = User.objects.filter(is_staff=False)
        user_stats = []

        for user in team_members:
            user_ratings = [r for r in all_ratings if r.user_id == user.id]
            agreements = 0
            disagreements = 0
            contrarian_movies = []  # Movies where user disagreed with consensus

            for rating in user_ratings:
                if rating.item_id in item_consensus:
                    consensus = item_consensus[rating.item_id]
                    if rating.rating == consensus:
                        agreements += 1
                    else:
                        disagreements += 1
                        contrarian_movies.append({
                            'item': rating.item,
                            'user_rating': rating.rating,
                            'consensus': consensus,
                        })

            total = agreements + disagreements
            if total >= 3:  # Need at least 3 comparable ratings
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
    """View showing movies with the most disagreement (high standard deviation in ratings)."""
    template_name = 'catalog/divisive.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = get_object_or_404(Category, slug=self.kwargs['slug'])
        context['category'] = category

        # Get all items with rating statistics
        items = Item.objects.filter(category=category).annotate(
            loved_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.LOVED)),
            liked_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.LIKED)),
            okay_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.OKAY)),
            disliked_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.DISLIKED)),
            hated_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.HATED)),
        ).prefetch_related('ratings')

        # Calculate divisiveness using standard deviation for each movie
        divisive_movies = []

        for item in items:
            # Get all ratings for this item (excluding NO_RATING)
            ratings = [r for r in item.ratings.all() if r.rating != Rating.Level.NO_RATING]

            if len(ratings) >= 5:  # Need at least 5 ratings to be considered
                # Convert ratings to numeric values (-2 to +2)
                values = [r.get_numeric_value() for r in ratings]

                # Calculate mean
                mean = sum(values) / len(values)

                # Calculate standard deviation
                variance = sum((x - mean) ** 2 for x in values) / len(values)
                std_dev = variance ** 0.5

                # Calculate percentages
                total_ratings = len(ratings)
                loved_percent = round((item.loved_count / total_ratings) * 100)
                liked_percent = round((item.liked_count / total_ratings) * 100)
                okay_percent = round((item.okay_count / total_ratings) * 100)
                disliked_percent = round((item.disliked_count / total_ratings) * 100)
                hated_percent = round((item.hated_count / total_ratings) * 100)

                divisive_movies.append({
                    'item': item,
                    'loved_count': item.loved_count,
                    'liked_count': item.liked_count,
                    'okay_count': item.okay_count,
                    'disliked_count': item.disliked_count,
                    'hated_count': item.hated_count,
                    'total_ratings': total_ratings,
                    'std_dev': round(std_dev, 2),
                    'loved_percent': loved_percent,
                    'liked_percent': liked_percent,
                    'okay_percent': okay_percent,
                    'disliked_percent': disliked_percent,
                    'hated_percent': hated_percent,
                })

        # Sort by standard deviation (highest first = most divisive)
        divisive_movies.sort(key=lambda x: (
            -x['std_dev'],           # Highest standard deviation first
            -x['total_ratings'],     # More ratings as tiebreaker
            x['item'].title.lower()
        ))

        context['divisive_movies'] = divisive_movies
        context['has_data'] = len(divisive_movies) > 0

        return context


class ItemDetailView(TemplateView):
    """View showing how everyone rated a specific item."""
    template_name = 'catalog/movie_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = get_object_or_404(Category, slug=self.kwargs['category_slug'])
        item = get_object_or_404(Item, id=self.kwargs['item_id'], category=category)

        context['category'] = category
        context['item'] = item

        # Get current user's rating if authenticated
        user_rating = None
        if self.request.user.is_authenticated:
            try:
                user_rating = Rating.objects.get(item=item, user=self.request.user)
                context['user_rating'] = user_rating.rating
            except Rating.DoesNotExist:
                context['user_rating'] = Rating.Level.NO_RATING

        # Get all ratings for this item, grouped by rating level
        all_ratings = Rating.objects.filter(item=item).select_related('user').order_by('user__last_name', 'user__first_name')

        # Group ratings by level
        loved_ratings = []
        liked_ratings = []
        okay_ratings = []
        disliked_ratings = []
        hated_ratings = []
        not_rated_ratings = []

        for rating in all_ratings:
            if rating.rating == Rating.Level.LOVED:
                loved_ratings.append(rating)
            elif rating.rating == Rating.Level.LIKED:
                liked_ratings.append(rating)
            elif rating.rating == Rating.Level.OKAY:
                okay_ratings.append(rating)
            elif rating.rating == Rating.Level.DISLIKED:
                disliked_ratings.append(rating)
            elif rating.rating == Rating.Level.HATED:
                hated_ratings.append(rating)
            elif rating.rating == Rating.Level.NO_RATING:
                not_rated_ratings.append(rating)

        # Get all team members who haven't rated yet
        team_members = User.objects.filter(is_staff=False)
        rated_user_ids = set(rating.user_id for rating in all_ratings)
        no_rating_users = [user for user in team_members if user.id not in rated_user_ids]
        no_rating_users.sort(key=lambda x: (x.last_name, x.first_name))

        context['loved_ratings'] = loved_ratings
        context['liked_ratings'] = liked_ratings
        context['okay_ratings'] = okay_ratings
        context['disliked_ratings'] = disliked_ratings
        context['hated_ratings'] = hated_ratings
        context['not_rated_ratings'] = not_rated_ratings
        context['no_rating_users'] = no_rating_users

        # Calculate statistics
        total_ratings = (len(loved_ratings) + len(liked_ratings) + len(okay_ratings) +
                        len(disliked_ratings) + len(hated_ratings))
        context['total_ratings'] = total_ratings
        context['loved_count'] = len(loved_ratings)
        context['liked_count'] = len(liked_ratings)
        context['okay_count'] = len(okay_ratings)
        context['disliked_count'] = len(disliked_ratings)
        context['hated_count'] = len(hated_ratings)
        context['not_rated_count'] = len(not_rated_ratings)
        context['no_rating_count'] = len(no_rating_users)

        if total_ratings > 0:
            context['loved_percent'] = round((len(loved_ratings) / total_ratings) * 100)
            context['liked_percent'] = round((len(liked_ratings) / total_ratings) * 100)
            context['okay_percent'] = round((len(okay_ratings) / total_ratings) * 100)
            context['disliked_percent'] = round((len(disliked_ratings) / total_ratings) * 100)
            context['hated_percent'] = round((len(hated_ratings) / total_ratings) * 100)
        else:
            context['loved_percent'] = 0
            context['liked_percent'] = 0
            context['okay_percent'] = 0
            context['disliked_percent'] = 0
            context['hated_percent'] = 0

        return context
