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


class TasteMapView(TemplateView):
    """View showing users clustered by taste using hierarchical clustering."""
    template_name = 'catalog/taste_map.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = get_object_or_404(Category, slug=self.kwargs['slug'])
        context['category'] = category

        # Get all team members
        team_members = list(User.objects.filter(is_staff=False).order_by('id'))

        if len(team_members) < 2:
            context['has_data'] = False
            context['error_message'] = "Need at least 2 team members for clustering."
            return context

        # Get all votes (excluding NO_ANSWER)
        votes = Vote.objects.filter(
            item__category=category
        ).exclude(choice=Vote.Choice.NO_ANSWER)

        # Build vote lookup: (user_id, item_id) -> vote_value
        vote_map = {}
        for vote in votes:
            if vote.choice == Vote.Choice.YES:
                value = 1
            elif vote.choice == Vote.Choice.NO:
                value = -1
            else:  # MEH
                value = 0
            vote_map[(vote.user_id, vote.item_id)] = value

        # Filter to users who have voted
        valid_users = [u for u in team_members if any(
            (u.id, item_id) in vote_map for item_id in set(k[1] for k in vote_map.keys())
        )]

        if len(valid_users) < 2:
            context['has_data'] = False
            context['error_message'] = "Need at least 2 team members with votes for clustering."
            return context

        # Compute pairwise similarity between users
        # Similarity = agreement rate on movies both have seen
        def compute_similarity(user1_id, user2_id):
            user1_votes = {k[1]: v for k, v in vote_map.items() if k[0] == user1_id}
            user2_votes = {k[1]: v for k, v in vote_map.items() if k[0] == user2_id}
            common_items = set(user1_votes.keys()) & set(user2_votes.keys())
            if not common_items:
                return 0.5  # Neutral if no common movies
            agreements = sum(1 for item_id in common_items if user1_votes[item_id] == user2_votes[item_id])
            return agreements / len(common_items)

        # Build distance matrix (distance = 1 - similarity)
        n = len(valid_users)
        dist_matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                sim = compute_similarity(valid_users[i].id, valid_users[j].id)
                dist = 1 - sim
                dist_matrix[i][j] = dist
                dist_matrix[j][i] = dist

        # Agglomerative hierarchical clustering (average linkage)
        # Each cluster is represented as (members, height)
        clusters = [{i} for i in range(n)]
        cluster_heights = [0.0] * n
        merge_history = []  # [(cluster1_idx, cluster2_idx, height, new_cluster_idx)]

        while len(clusters) > 1:
            # Find closest pair of clusters
            min_dist = float('inf')
            merge_i, merge_j = 0, 1
            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    # Average linkage: average distance between all pairs
                    total_dist = 0
                    count = 0
                    for mi in clusters[i]:
                        for mj in clusters[j]:
                            total_dist += dist_matrix[mi][mj]
                            count += 1
                    avg_dist = total_dist / count if count > 0 else 0
                    if avg_dist < min_dist:
                        min_dist = avg_dist
                        merge_i, merge_j = i, j

            # Merge clusters
            new_cluster = clusters[merge_i] | clusters[merge_j]
            new_height = min_dist
            new_idx = len(cluster_heights)
            cluster_heights.append(new_height)

            merge_history.append({
                'left': merge_i if merge_i < n else merge_i,
                'right': merge_j if merge_j < n else merge_j,
                'height': new_height,
                'left_height': cluster_heights[merge_i] if merge_i < len(cluster_heights) else 0,
                'right_height': cluster_heights[merge_j] if merge_j < len(cluster_heights) else 0,
                'members': list(new_cluster),
            })

            # Update clusters list
            clusters = [c for idx, c in enumerate(clusters) if idx not in (merge_i, merge_j)]
            clusters.append(new_cluster)
            # Track index mapping
            cluster_heights[merge_i] = new_height
            cluster_heights[merge_j] = new_height

        # Build dendrogram data for visualization
        colors = [
            '#8B5CF6', '#EC4899', '#F59E0B', '#10B981', '#3B82F6',
            '#EF4444', '#06B6D4', '#F97316', '#84CC16', '#6366F1',
        ]

        user_data = []
        for i, user in enumerate(valid_users):
            vote_count = sum(1 for k in vote_map.keys() if k[0] == user.id)
            user_data.append({
                'id': i,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'full_name': f"{user.first_name} {user.last_name}",
                'color': colors[i % len(colors)],
                'vote_count': vote_count,
            })

        # Build dendrogram structure for D3-style rendering
        # We need to convert merge_history into a tree structure
        def build_tree(merge_idx):
            if merge_idx < 0:
                return None
            merge = merge_history[merge_idx]
            return merge

        # Calculate similarity percentages for display
        similarity_data = []
        for i in range(n):
            for j in range(i + 1, n):
                sim = compute_similarity(valid_users[i].id, valid_users[j].id)
                similarity_data.append({
                    'user1': user_data[i]['full_name'],
                    'user2': user_data[j]['full_name'],
                    'similarity': round(sim * 100),
                })
        similarity_data.sort(key=lambda x: -x['similarity'])

        context['user_data'] = user_data
        context['user_data_json'] = json.dumps(user_data)
        context['merge_history'] = merge_history
        context['merge_history_json'] = json.dumps(merge_history)
        context['similarity_data'] = similarity_data[:10]  # Top 10 pairs
        context['has_data'] = True
        context['user_count'] = len(valid_users)

        return context
