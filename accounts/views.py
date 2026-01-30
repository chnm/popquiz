from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.views.generic import CreateView, DetailView
from django.views import View
from django.urls import reverse_lazy, reverse
from django.db.models import Count

from .forms import RegistrationForm
from .models import User
from votes.models import Vote


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

        # Get votes with vote counts for popularity sorting
        votes = Vote.objects.filter(user=profile_user).exclude(
            choice=Vote.Choice.NO_ANSWER
        ).select_related('item__category', 'item').annotate(
            item_vote_count=Count('item__votes')
        )

        # Organize votes by category
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
