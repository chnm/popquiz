from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.views.generic import CreateView, DetailView
from django.urls import reverse_lazy
from django.db.models import Count

from .forms import RegistrationForm
from .models import User
from votes.models import Vote


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

        return context
