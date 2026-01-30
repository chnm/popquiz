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
from .imdb_utils import fetch_movie_data
from votes.models import Vote


class HomeView(ListView):
    model = Category
    template_name = 'catalog/home.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return Category.objects.annotate(item_count=Count('items'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['users'] = User.objects.filter(is_staff=False).order_by('last_name', 'first_name')

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
                categories_with_progress.append({
                    'category': category,
                    'total': total_items,
                    'voted': responded_count,
                    'remaining': remaining,
                    'progress_percent': progress_percent,
                })
            context['categories_with_progress'] = categories_with_progress

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

        # Calculate scores for all movies
        ranked_movies = []

        for item in items:
            # Total votes = only those who actually watched (yes + no + meh)
            total_votes = item.yes_count + item.no_count + item.meh_count
            if total_votes > 0:
                # Score from -100 to +100
                score = round(((item.yes_count - item.no_count) / total_votes) * 100)
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

        # Group movies by decade
        decades = {}
        no_year = []

        for item in items:
            total_votes = item.yes_count + item.no_count + item.meh_count
            if total_votes > 0:
                score = round(((item.yes_count - item.no_count) / total_votes) * 100)
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
