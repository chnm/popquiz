from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.views.generic import CreateView, DetailView
from django.views import View
from django.urls import reverse_lazy, reverse
from django.db.models import Count, Q

from .forms import RegistrationForm, LoginForm
from .models import User
from votes.models import Vote
from catalog.models import Item


def calculate_compatibility(user1, user2):
    """
    Calculate compatibility between two users based on their votes.
    Returns a dict with compatibility score and vote breakdowns.
    """
    # Get votes for both users (excluding "haven't watched")
    user1_votes = {
        v.item_id: v.choice
        for v in Vote.objects.filter(user=user1).exclude(choice=Vote.Choice.NO_ANSWER)
    }
    user2_votes = {
        v.item_id: v.choice
        for v in Vote.objects.filter(user=user2).exclude(choice=Vote.Choice.NO_ANSWER)
    }

    # Find common items (both have watched)
    common_items = set(user1_votes.keys()) & set(user2_votes.keys())

    if not common_items:
        return {
            'score': None,
            'common_count': 0,
            'agree_count': 0,
            'disagree_count': 0,
        }

    # Count agreements and disagreements
    both_yes = 0
    both_no = 0
    both_meh = 0
    disagree = 0

    for item_id in common_items:
        v1, v2 = user1_votes[item_id], user2_votes[item_id]
        if v1 == v2:
            if v1 == Vote.Choice.YES:
                both_yes += 1
            elif v1 == Vote.Choice.NO:
                both_no += 1
            else:
                both_meh += 1
        else:
            disagree += 1

    agree_count = both_yes + both_no + both_meh
    total = len(common_items)
    score = round((agree_count / total) * 100) if total > 0 else 0

    return {
        'score': score,
        'common_count': total,
        'agree_count': agree_count,
        'disagree_count': disagree,
        'both_yes': both_yes,
        'both_no': both_no,
        'both_meh': both_meh,
    }


class RegisterView(CreateView):
    form_class = RegistrationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, f'Welcome to PopQuiz, {user.first_name}!')
        return redirect(self.success_url)


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    form_class = LoginForm

    def get_success_url(self):
        return reverse_lazy('home')

    def form_valid(self, form):
        messages.success(self.request, f'Welcome back, {form.get_user().first_name}!')
        return super().form_valid(form)


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('home')

    def dispatch(self, request, *args, **kwargs):
        messages.info(request, 'You have been logged out.')
        return super().dispatch(request, *args, **kwargs)


class ProfileView(DetailView):
    model = User
    template_name = 'accounts/profile.html'
    context_object_name = 'profile_user'
    slug_field = 'username'
    slug_url_kwarg = 'username'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile_user = self.object
        sort_by = self.request.GET.get('sort', 'title')
        context['current_sort'] = sort_by

        # For director and genre views, include NO_ANSWER to show movies not yet seen
        # For other views, exclude NO_ANSWER to only show rated movies
        if sort_by in ['director', 'genre']:
            votes = Vote.objects.filter(user=profile_user).select_related(
                'item__category', 'item'
            ).annotate(
                item_vote_count=Count('item__votes')
            )
        else:
            votes = Vote.objects.filter(user=profile_user).exclude(
                choice=Vote.Choice.NO_ANSWER
            ).select_related('item__category', 'item').annotate(
                item_vote_count=Count('item__votes')
            )

        # Group votes by director, genre, or category depending on sort
        if sort_by == 'director':
            # Group by director (includes not-seen movies)
            votes_by_category = {}
            for vote in votes:
                director = vote.item.director if vote.item.director else 'Unknown Director'
                if director not in votes_by_category:
                    votes_by_category[director] = {
                        'slug': None,  # No slug for directors
                        'votes': [],
                        'yes_count': 0,
                        'no_count': 0,
                        'meh_count': 0,
                        'not_seen_count': 0,
                    }
                votes_by_category[director]['votes'].append(vote)
                if vote.choice == Vote.Choice.YES:
                    votes_by_category[director]['yes_count'] += 1
                elif vote.choice == Vote.Choice.NO:
                    votes_by_category[director]['no_count'] += 1
                elif vote.choice == Vote.Choice.MEH:
                    votes_by_category[director]['meh_count'] += 1
                elif vote.choice == Vote.Choice.NO_ANSWER:
                    votes_by_category[director]['not_seen_count'] += 1

            # Sort directors alphabetically and sort movies within each director by title
            votes_by_category = dict(sorted(votes_by_category.items(), key=lambda x: x[0].lower()))
            for director_name, director_data in votes_by_category.items():
                director_data['votes'].sort(key=lambda v: v.item.title.lower())

        elif sort_by == 'genre':
            # Group by genre (movies can appear under multiple genres, includes not-seen)
            votes_by_category = {}
            for vote in votes:
                genres = vote.item.genre.split(',') if vote.item.genre else ['Unknown Genre']
                # Clean up genre names
                genres = [g.strip() for g in genres]

                for genre in genres:
                    if genre not in votes_by_category:
                        votes_by_category[genre] = {
                            'slug': None,  # No slug for genres
                            'votes': [],
                            'yes_count': 0,
                            'no_count': 0,
                            'meh_count': 0,
                            'not_seen_count': 0,
                        }
                    # Only add the vote if it's not already in this genre's list
                    if vote not in votes_by_category[genre]['votes']:
                        votes_by_category[genre]['votes'].append(vote)
                        if vote.choice == Vote.Choice.YES:
                            votes_by_category[genre]['yes_count'] += 1
                        elif vote.choice == Vote.Choice.NO:
                            votes_by_category[genre]['no_count'] += 1
                        elif vote.choice == Vote.Choice.MEH:
                            votes_by_category[genre]['meh_count'] += 1
                        elif vote.choice == Vote.Choice.NO_ANSWER:
                            votes_by_category[genre]['not_seen_count'] += 1

            # Sort genres alphabetically and sort movies within each genre by title
            votes_by_category = dict(sorted(votes_by_category.items(), key=lambda x: x[0].lower()))
            for genre_name, genre_data in votes_by_category.items():
                genre_data['votes'].sort(key=lambda v: v.item.title.lower())

        else:
            # Original behavior: organize by category
            votes_by_category = {}
            for vote in votes:
                category_name = vote.item.category.name
                category_slug = vote.item.category.slug
                if category_name not in votes_by_category:
                    votes_by_category[category_name] = {
                        'slug': category_slug,
                        'votes': [],
                        'yes_count': 0,
                        'no_count': 0,
                        'meh_count': 0,
                    }
                votes_by_category[category_name]['votes'].append(vote)
                if vote.choice == Vote.Choice.YES:
                    votes_by_category[category_name]['yes_count'] += 1
                elif vote.choice == Vote.Choice.NO:
                    votes_by_category[category_name]['no_count'] += 1
                elif vote.choice == Vote.Choice.MEH:
                    votes_by_category[category_name]['meh_count'] += 1

            # Sort votes within each category
            vote_order = {'yes': 0, 'meh': 1, 'no': 2}
            for category_name, category_data in votes_by_category.items():
                if sort_by == 'title':
                    category_data['votes'].sort(key=lambda v: v.item.title.lower())
                elif sort_by == 'year':
                    category_data['votes'].sort(key=lambda v: (v.item.year or 0, v.item.title.lower()))
                elif sort_by == 'vote':
                    category_data['votes'].sort(key=lambda v: (vote_order.get(v.choice, 3), v.item.title.lower()))
                elif sort_by == 'popularity':
                    category_data['votes'].sort(key=lambda v: (-v.item_vote_count, v.item.title.lower()))

        # Calculate totals
        total_yes = sum(cat['yes_count'] for cat in votes_by_category.values())
        total_no = sum(cat['no_count'] for cat in votes_by_category.values())
        total_meh = sum(cat['meh_count'] for cat in votes_by_category.values())
        total_votes = total_yes + total_no + total_meh

        context['votes_by_category'] = votes_by_category
        context['total_yes'] = total_yes
        context['total_no'] = total_no
        context['total_meh'] = total_meh
        context['total_votes'] = total_votes

        # Percentages for the visual bars
        if total_votes > 0:
            context['yes_percent'] = round(total_yes / total_votes * 100)
            context['no_percent'] = round(total_no / total_votes * 100)
            context['meh_percent'] = round(total_meh / total_votes * 100)
        else:
            context['yes_percent'] = 0
            context['no_percent'] = 0
            context['meh_percent'] = 0

        # Calculate compatibility with other users
        other_users = User.objects.filter(is_staff=False).exclude(id=profile_user.id)
        compatibilities = []

        for other_user in other_users:
            compat = calculate_compatibility(profile_user, other_user)
            if compat['score'] is not None:
                compatibilities.append({
                    'user': other_user,
                    **compat
                })

        # Sort by score
        compatibilities.sort(key=lambda x: -x['score'])

        if compatibilities:
            context['most_compatible'] = compatibilities[0]
            context['least_compatible'] = compatibilities[-1]
            context['all_compatibilities'] = compatibilities

        # Get unseen movies ranked by team ratings
        # Get all movies the user has voted on (including NO_ANSWER)
        voted_item_ids = Vote.objects.filter(user=profile_user).values_list('item_id', flat=True)

        # Get all items the user hasn't voted on
        unseen_items = Item.objects.exclude(id__in=voted_item_ids).annotate(
            yes_count=Count('votes', filter=Q(votes__choice=Vote.Choice.YES)),
            no_count=Count('votes', filter=Q(votes__choice=Vote.Choice.NO)),
            meh_count=Count('votes', filter=Q(votes__choice=Vote.Choice.MEH)),
        )

        # Calculate global average score (for Bayesian average)
        total_yes = 0
        total_no = 0
        total_meh = 0
        all_items_for_avg = Item.objects.annotate(
            yes_count=Count('votes', filter=Q(votes__choice=Vote.Choice.YES)),
            no_count=Count('votes', filter=Q(votes__choice=Vote.Choice.NO)),
            meh_count=Count('votes', filter=Q(votes__choice=Vote.Choice.MEH)),
        )
        for item in all_items_for_avg:
            total_yes += item.yes_count
            total_no += item.no_count
            total_meh += item.meh_count

        total_all_votes = total_yes + total_no + total_meh
        if total_all_votes > 0:
            global_average = ((total_yes - total_no) / total_all_votes) * 100
        else:
            global_average = 0

        C = 5  # Confidence parameter

        # Calculate scores for unseen movies
        unseen_ranked = []
        for item in unseen_items:
            total_item_votes = item.yes_count + item.no_count + item.meh_count
            if total_item_votes > 0:
                raw_score = ((item.yes_count - item.no_count) / total_item_votes) * 100
                bayesian_score = (C * global_average + total_item_votes * raw_score) / (C + total_item_votes)
                score = round(bayesian_score)

                unseen_ranked.append({
                    'item': item,
                    'score': score,
                    'yes_count': item.yes_count,
                    'no_count': item.no_count,
                    'meh_count': item.meh_count,
                    'total_votes': total_item_votes,
                })

        # Sort by score (highest first), then by vote count, then by title
        unseen_ranked.sort(key=lambda x: (
            -x['score'],
            -x['yes_count'],
            x['item'].title.lower()
        ))

        context['unseen_movies'] = unseen_ranked[:20]  # Limit to top 20

        # Get random movie posters from movies the user loved for header background
        loved_items_with_posters = Item.objects.filter(
            votes__user=profile_user,
            votes__choice=Vote.Choice.YES
        ).exclude(
            poster_url=''
        ).distinct().order_by('?')[:5]
        context['random_posters'] = loved_items_with_posters

        return context


class CompareUsersView(View):
    """View to compare two users' movie preferences."""

    def get(self, request, username1, username2):
        user1 = get_object_or_404(User, username=username1)
        user2 = get_object_or_404(User, username=username2)

        # Get votes for both users
        user1_votes = {
            v.item_id: {'choice': v.choice, 'item': v.item}
            for v in Vote.objects.filter(user=user1).exclude(
                choice=Vote.Choice.NO_ANSWER
            ).select_related('item', 'item__category')
        }
        user2_votes = {
            v.item_id: {'choice': v.choice, 'item': v.item}
            for v in Vote.objects.filter(user=user2).exclude(
                choice=Vote.Choice.NO_ANSWER
            ).select_related('item', 'item__category')
        }

        # Categorize movies
        both_love = []      # Both voted yes
        both_hate = []      # Both voted no
        both_meh = []       # Both voted meh
        user1_loves_user2_hates = []  # user1 yes, user2 no
        user1_hates_user2_loves = []  # user1 no, user2 yes
        other_disagreements = []      # Other disagreements (involving meh)
        only_user1 = []     # Only user1 has watched
        only_user2 = []     # Only user2 has watched

        all_items = set(user1_votes.keys()) | set(user2_votes.keys())

        for item_id in all_items:
            in_user1 = item_id in user1_votes
            in_user2 = item_id in user2_votes

            if in_user1 and in_user2:
                v1 = user1_votes[item_id]['choice']
                v2 = user2_votes[item_id]['choice']
                item = user1_votes[item_id]['item']

                if v1 == v2:
                    if v1 == Vote.Choice.YES:
                        both_love.append(item)
                    elif v1 == Vote.Choice.NO:
                        both_hate.append(item)
                    else:
                        both_meh.append(item)
                else:
                    if v1 == Vote.Choice.YES and v2 == Vote.Choice.NO:
                        user1_loves_user2_hates.append(item)
                    elif v1 == Vote.Choice.NO and v2 == Vote.Choice.YES:
                        user1_hates_user2_loves.append(item)
                    else:
                        other_disagreements.append({'item': item, 'v1': v1, 'v2': v2})
            elif in_user1:
                only_user1.append(user1_votes[item_id]['item'])
            else:
                only_user2.append(user2_votes[item_id]['item'])

        # Sort all lists by title
        for lst in [both_love, both_hate, both_meh, user1_loves_user2_hates,
                    user1_hates_user2_loves, only_user1, only_user2]:
            lst.sort(key=lambda x: x.title.lower())
        other_disagreements.sort(key=lambda x: x['item'].title.lower())

        # Calculate compatibility
        compat = calculate_compatibility(user1, user2)

        return render(request, 'accounts/compare.html', {
            'user1': user1,
            'user2': user2,
            'compatibility': compat,
            'both_love': both_love,
            'both_hate': both_hate,
            'both_meh': both_meh,
            'user1_loves_user2_hates': user1_loves_user2_hates,
            'user1_hates_user2_loves': user1_hates_user2_loves,
            'other_disagreements': other_disagreements,
            'only_user1': only_user1,
            'only_user2': only_user2,
        })


class CompareThreeUsersView(View):
    """View to compare three users' movie preferences with a 3-way Venn diagram."""

    def get(self, request, username1, username2, username3):
        user1 = get_object_or_404(User, username=username1)
        user2 = get_object_or_404(User, username=username2)
        user3 = get_object_or_404(User, username=username3)

        # Get votes for all three users
        user1_votes = {
            v.item_id: {'choice': v.choice, 'item': v.item}
            for v in Vote.objects.filter(user=user1).exclude(
                choice=Vote.Choice.NO_ANSWER
            ).select_related('item', 'item__category')
        }
        user2_votes = {
            v.item_id: {'choice': v.choice, 'item': v.item}
            for v in Vote.objects.filter(user=user2).exclude(
                choice=Vote.Choice.NO_ANSWER
            ).select_related('item', 'item__category')
        }
        user3_votes = {
            v.item_id: {'choice': v.choice, 'item': v.item}
            for v in Vote.objects.filter(user=user3).exclude(
                choice=Vote.Choice.NO_ANSWER
            ).select_related('item', 'item__category')
        }

        # Seven regions for 3-way Venn diagram
        only_user1 = []
        only_user2 = []
        only_user3 = []
        user1_and_2 = {'all_love': [], 'all_hate': [], 'all_meh': [], 'mixed': []}
        user1_and_3 = {'all_love': [], 'all_hate': [], 'all_meh': [], 'mixed': []}
        user2_and_3 = {'all_love': [], 'all_hate': [], 'all_meh': [], 'mixed': []}
        all_three = {'all_love': [], 'all_hate': [], 'all_meh': [], 'mixed': []}

        all_items = set(user1_votes.keys()) | set(user2_votes.keys()) | set(user3_votes.keys())

        for item_id in all_items:
            in_user1 = item_id in user1_votes
            in_user2 = item_id in user2_votes
            in_user3 = item_id in user3_votes

            # Determine which region this item belongs to
            if in_user1 and in_user2 and in_user3:
                # All three watched
                v1 = user1_votes[item_id]['choice']
                v2 = user2_votes[item_id]['choice']
                v3 = user3_votes[item_id]['choice']
                item = user1_votes[item_id]['item']

                if v1 == v2 == v3:
                    if v1 == Vote.Choice.YES:
                        all_three['all_love'].append(item)
                    elif v1 == Vote.Choice.NO:
                        all_three['all_hate'].append(item)
                    else:
                        all_three['all_meh'].append(item)
                else:
                    all_three['mixed'].append({'item': item, 'v1': v1, 'v2': v2, 'v3': v3})

            elif in_user1 and in_user2 and not in_user3:
                # User 1 & 2 only
                v1 = user1_votes[item_id]['choice']
                v2 = user2_votes[item_id]['choice']
                item = user1_votes[item_id]['item']

                if v1 == v2:
                    if v1 == Vote.Choice.YES:
                        user1_and_2['all_love'].append(item)
                    elif v1 == Vote.Choice.NO:
                        user1_and_2['all_hate'].append(item)
                    else:
                        user1_and_2['all_meh'].append(item)
                else:
                    user1_and_2['mixed'].append({'item': item, 'v1': v1, 'v2': v2})

            elif in_user1 and in_user3 and not in_user2:
                # User 1 & 3 only
                v1 = user1_votes[item_id]['choice']
                v3 = user3_votes[item_id]['choice']
                item = user1_votes[item_id]['item']

                if v1 == v3:
                    if v1 == Vote.Choice.YES:
                        user1_and_3['all_love'].append(item)
                    elif v1 == Vote.Choice.NO:
                        user1_and_3['all_hate'].append(item)
                    else:
                        user1_and_3['all_meh'].append(item)
                else:
                    user1_and_3['mixed'].append({'item': item, 'v1': v1, 'v3': v3})

            elif in_user2 and in_user3 and not in_user1:
                # User 2 & 3 only
                v2 = user2_votes[item_id]['choice']
                v3 = user3_votes[item_id]['choice']
                item = user2_votes[item_id]['item']

                if v2 == v3:
                    if v2 == Vote.Choice.YES:
                        user2_and_3['all_love'].append(item)
                    elif v2 == Vote.Choice.NO:
                        user2_and_3['all_hate'].append(item)
                    else:
                        user2_and_3['all_meh'].append(item)
                else:
                    user2_and_3['mixed'].append({'item': item, 'v2': v2, 'v3': v3})

            elif in_user1 and not in_user2 and not in_user3:
                only_user1.append(user1_votes[item_id]['item'])
            elif in_user2 and not in_user1 and not in_user3:
                only_user2.append(user2_votes[item_id]['item'])
            elif in_user3 and not in_user1 and not in_user2:
                only_user3.append(user3_votes[item_id]['item'])

        # Sort all lists by title
        only_user1.sort(key=lambda x: x.title.lower())
        only_user2.sort(key=lambda x: x.title.lower())
        only_user3.sort(key=lambda x: x.title.lower())

        for region in [user1_and_2, user1_and_3, user2_and_3, all_three]:
            for category in ['all_love', 'all_hate', 'all_meh']:
                region[category].sort(key=lambda x: x.title.lower())
            region['mixed'].sort(key=lambda x: x['item'].title.lower())

        # Calculate statistics
        total_all_three = (len(all_three['all_love']) + len(all_three['all_hate']) +
                          len(all_three['all_meh']) + len(all_three['mixed']))
        total_user1_and_2 = (len(user1_and_2['all_love']) + len(user1_and_2['all_hate']) +
                            len(user1_and_2['all_meh']) + len(user1_and_2['mixed']))
        total_user1_and_3 = (len(user1_and_3['all_love']) + len(user1_and_3['all_hate']) +
                            len(user1_and_3['all_meh']) + len(user1_and_3['mixed']))
        total_user2_and_3 = (len(user2_and_3['all_love']) + len(user2_and_3['all_hate']) +
                            len(user2_and_3['all_meh']) + len(user2_and_3['mixed']))

        return render(request, 'accounts/compare_three.html', {
            'user1': user1,
            'user2': user2,
            'user3': user3,
            'only_user1': only_user1,
            'only_user2': only_user2,
            'only_user3': only_user3,
            'user1_and_2': user1_and_2,
            'user1_and_3': user1_and_3,
            'user2_and_3': user2_and_3,
            'all_three': all_three,
            'total_all_three': total_all_three,
            'total_user1_and_2': total_user1_and_2,
            'total_user1_and_3': total_user1_and_3,
            'total_user2_and_3': total_user2_and_3,
        })
