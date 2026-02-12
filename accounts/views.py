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
from ratings.models import Rating
from catalog.models import Item


def calculate_compatibility(user1, user2):
    """
    Calculate compatibility between two users based on their ratings.
    Uses positive/negative/neutral categorization for all rating types.
    Returns a dict with compatibility score and rating breakdowns.
    """
    def categorize_rating(rating):
        """Categorize a rating as positive, negative, or neutral."""
        if rating in [Rating.Level.LOVED, Rating.Level.LIKED]:
            return 'positive'
        elif rating in [Rating.Level.HATED, Rating.Level.DISLIKED]:
            return 'negative'
        elif rating == Rating.Level.OKAY:
            return 'neutral'
        return None

    # Get all ratings for both users (excluding NO_RATING)
    user1_ratings = {
        r.item_id: r.rating
        for r in Rating.objects.filter(
            user=user1
        ).exclude(
            rating=Rating.Level.NO_RATING
        )
    }
    user2_ratings = {
        r.item_id: r.rating
        for r in Rating.objects.filter(
            user=user2
        ).exclude(
            rating=Rating.Level.NO_RATING
        )
    }

    # Find common items (both have rated)
    common_items = set(user1_ratings.keys()) & set(user2_ratings.keys())

    if not common_items:
        return {
            'score': None,
            'common_count': 0,
            'agree_count': 0,
            'disagree_count': 0,
        }

    # Count agreements and disagreements using categories
    agree_count = 0
    disagree_count = 0

    for item_id in common_items:
        r1 = user1_ratings[item_id]
        r2 = user2_ratings[item_id]
        cat1 = categorize_rating(r1)
        cat2 = categorize_rating(r2)

        if cat1 == cat2:
            agree_count += 1
        else:
            disagree_count += 1

    total = len(common_items)
    score = round((agree_count / total) * 100) if total > 0 else 0

    return {
        'score': score,
        'common_count': total,
        'agree_count': agree_count,
        'disagree_count': disagree_count,
    }


class RegisterView(CreateView):
    form_class = RegistrationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        display_name = user.first_name if user.first_name else user.username
        messages.success(self.request, f'Welcome to PopQuiz, {display_name}!')
        return redirect(self.success_url)


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    form_class = LoginForm

    def get_success_url(self):
        return reverse_lazy('home')

    def form_valid(self, form):
        user = form.get_user()
        display_name = user.first_name if user.first_name else user.username
        messages.success(self.request, f'Welcome back, {display_name}!')
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

        # For director and genre views, include NO_RATING to show movies not yet rated
        # For other views, exclude NO_RATING to only show rated movies
        if sort_by in ['director', 'genre']:
            ratings = Rating.objects.filter(user=profile_user).select_related(
                'item__category', 'item'
            ).annotate(
                item_rating_count=Count('item__ratings')
            )
        else:
            ratings = Rating.objects.filter(user=profile_user).exclude(
                rating=Rating.Level.NO_RATING
            ).select_related('item__category', 'item').annotate(
                item_rating_count=Count('item__ratings')
            )

        # Group ratings by director, genre, or category depending on sort
        if sort_by == 'director':
            # Group by director (includes not-rated movies)
            ratings_by_category = {}
            for rating in ratings:
                director = rating.item.director if rating.item.director else 'Unknown Director'
                if director not in ratings_by_category:
                    ratings_by_category[director] = {
                        'slug': None,  # No slug for directors
                        'ratings': [],
                        'loved_count': 0,
                        'liked_count': 0,
                        'okay_count': 0,
                        'disliked_count': 0,
                        'hated_count': 0,
                        'not_rated_count': 0,
                    }
                ratings_by_category[director]['ratings'].append(rating)
                if rating.rating == Rating.Level.LOVED:
                    ratings_by_category[director]['loved_count'] += 1
                elif rating.rating == Rating.Level.LIKED:
                    ratings_by_category[director]['liked_count'] += 1
                elif rating.rating == Rating.Level.OKAY:
                    ratings_by_category[director]['okay_count'] += 1
                elif rating.rating == Rating.Level.DISLIKED:
                    ratings_by_category[director]['disliked_count'] += 1
                elif rating.rating == Rating.Level.HATED:
                    ratings_by_category[director]['hated_count'] += 1
                elif rating.rating == Rating.Level.NO_RATING:
                    ratings_by_category[director]['not_rated_count'] += 1

            # Sort directors alphabetically and sort movies within each director by title
            ratings_by_category = dict(sorted(ratings_by_category.items(), key=lambda x: x[0].lower()))
            for director_name, director_data in ratings_by_category.items():
                director_data['ratings'].sort(key=lambda r: r.item.title.lower())

        elif sort_by == 'genre':
            # Group by genre (movies can appear under multiple genres, includes not-rated)
            ratings_by_category = {}
            for rating in ratings:
                genres = rating.item.genre.split(',') if rating.item.genre else ['Unknown Genre']
                # Clean up genre names
                genres = [g.strip() for g in genres]

                for genre in genres:
                    if genre not in ratings_by_category:
                        ratings_by_category[genre] = {
                            'slug': None,  # No slug for genres
                            'ratings': [],
                            'loved_count': 0,
                            'liked_count': 0,
                            'okay_count': 0,
                            'disliked_count': 0,
                            'hated_count': 0,
                            'not_rated_count': 0,
                        }
                    # Only add the rating if it's not already in this genre's list
                    if rating not in ratings_by_category[genre]['ratings']:
                        ratings_by_category[genre]['ratings'].append(rating)
                        if rating.rating == Rating.Level.LOVED:
                            ratings_by_category[genre]['loved_count'] += 1
                        elif rating.rating == Rating.Level.LIKED:
                            ratings_by_category[genre]['liked_count'] += 1
                        elif rating.rating == Rating.Level.OKAY:
                            ratings_by_category[genre]['okay_count'] += 1
                        elif rating.rating == Rating.Level.DISLIKED:
                            ratings_by_category[genre]['disliked_count'] += 1
                        elif rating.rating == Rating.Level.HATED:
                            ratings_by_category[genre]['hated_count'] += 1
                        elif rating.rating == Rating.Level.NO_RATING:
                            ratings_by_category[genre]['not_rated_count'] += 1

            # Sort genres alphabetically and sort movies within each genre by title
            ratings_by_category = dict(sorted(ratings_by_category.items(), key=lambda x: x[0].lower()))
            for genre_name, genre_data in ratings_by_category.items():
                genre_data['ratings'].sort(key=lambda r: r.item.title.lower())

        else:
            # Original behavior: organize by category
            ratings_by_category = {}
            for rating in ratings:
                category_name = rating.item.category.name
                category_slug = rating.item.category.slug
                if category_name not in ratings_by_category:
                    ratings_by_category[category_name] = {
                        'slug': category_slug,
                        'ratings': [],
                        'loved_count': 0,
                        'liked_count': 0,
                        'okay_count': 0,
                        'disliked_count': 0,
                        'hated_count': 0,
                    }
                ratings_by_category[category_name]['ratings'].append(rating)
                if rating.rating == Rating.Level.LOVED:
                    ratings_by_category[category_name]['loved_count'] += 1
                elif rating.rating == Rating.Level.LIKED:
                    ratings_by_category[category_name]['liked_count'] += 1
                elif rating.rating == Rating.Level.OKAY:
                    ratings_by_category[category_name]['okay_count'] += 1
                elif rating.rating == Rating.Level.DISLIKED:
                    ratings_by_category[category_name]['disliked_count'] += 1
                elif rating.rating == Rating.Level.HATED:
                    ratings_by_category[category_name]['hated_count'] += 1

            # Sort ratings within each category
            rating_order = {
                Rating.Level.LOVED: 0,
                Rating.Level.LIKED: 1,
                Rating.Level.OKAY: 2,
                Rating.Level.DISLIKED: 3,
                Rating.Level.HATED: 4
            }
            for category_name, category_data in ratings_by_category.items():
                if sort_by == 'title':
                    category_data['ratings'].sort(key=lambda r: r.item.title.lower())
                elif sort_by == 'year':
                    category_data['ratings'].sort(key=lambda r: (r.item.year or 0, r.item.title.lower()))
                elif sort_by == 'vote':
                    category_data['ratings'].sort(key=lambda r: (rating_order.get(r.rating, 5), r.item.title.lower()))
                elif sort_by == 'popularity':
                    category_data['ratings'].sort(key=lambda r: (-r.item_rating_count, r.item.title.lower()))

        # Calculate totals
        total_loved = sum(cat['loved_count'] for cat in ratings_by_category.values())
        total_liked = sum(cat['liked_count'] for cat in ratings_by_category.values())
        total_okay = sum(cat['okay_count'] for cat in ratings_by_category.values())
        total_disliked = sum(cat['disliked_count'] for cat in ratings_by_category.values())
        total_hated = sum(cat['hated_count'] for cat in ratings_by_category.values())
        total_ratings = total_loved + total_liked + total_okay + total_disliked + total_hated

        context['ratings_by_category'] = ratings_by_category
        context['total_loved'] = total_loved
        context['total_liked'] = total_liked
        context['total_okay'] = total_okay
        context['total_disliked'] = total_disliked
        context['total_hated'] = total_hated
        context['total_ratings'] = total_ratings

        # Percentages for the visual bars
        if total_ratings > 0:
            context['loved_percent'] = round(total_loved / total_ratings * 100)
            context['liked_percent'] = round(total_liked / total_ratings * 100)
            context['okay_percent'] = round(total_okay / total_ratings * 100)
            context['disliked_percent'] = round(total_disliked / total_ratings * 100)
            context['hated_percent'] = round(total_hated / total_ratings * 100)
        else:
            context['loved_percent'] = 0
            context['liked_percent'] = 0
            context['okay_percent'] = 0
            context['disliked_percent'] = 0
            context['hated_percent'] = 0

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

        # Get unseen movies ranked by team ratings (using simple average)
        # Get all movies the user has rated (including NO_RATING)
        rated_item_ids = Rating.objects.filter(user=profile_user).values_list('item_id', flat=True)

        # Get all items the user hasn't rated
        unseen_items = Item.objects.exclude(id__in=rated_item_ids).annotate(
            loved_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.LOVED)),
            liked_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.LIKED)),
            okay_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.OKAY)),
            disliked_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.DISLIKED)),
            hated_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.HATED)),
        )

        # Calculate scores for unseen movies using simple average
        unseen_ranked = []
        for item in unseen_items:
            total_item_ratings = (item.loved_count + item.liked_count + item.okay_count +
                                item.disliked_count + item.hated_count)
            if total_item_ratings > 0:
                # Simple average: loved=2, liked=1, okay=0, disliked=-1, hated=-2
                total_value = (item.loved_count * 2 + item.liked_count * 1 +
                             item.okay_count * 0 + item.disliked_count * -1 +
                             item.hated_count * -2)
                average = total_value / total_item_ratings
                # Convert to 0-100 scale for display
                score = round(((average + 2) / 4) * 100)

                unseen_ranked.append({
                    'item': item,
                    'score': score,
                    'loved_count': item.loved_count,
                    'liked_count': item.liked_count,
                    'okay_count': item.okay_count,
                    'disliked_count': item.disliked_count,
                    'hated_count': item.hated_count,
                    'total_ratings': total_item_ratings,
                })

        # Sort by score (highest first), then by loved count, then by title
        unseen_ranked.sort(key=lambda x: (
            -x['score'],
            -x['loved_count'],
            x['item'].title.lower()
        ))

        context['unseen_movies'] = unseen_ranked[:20]  # Limit to top 20

        # Get random movie posters from movies the user loved for header background
        loved_items_with_posters = Item.objects.filter(
            ratings__user=profile_user,
            ratings__rating=Rating.Level.LOVED
        ).exclude(
            poster_url=''
        ).distinct().order_by('?')[:5]
        context['random_posters'] = loved_items_with_posters

        return context


class CompareUsersView(View):
    """View to compare two users' movie preferences (positive/negative/neutral)."""

    def _categorize_rating(self, rating):
        """Categorize a rating as positive, negative, or neutral."""
        if rating in [Rating.Level.LOVED, Rating.Level.LIKED]:
            return 'positive'
        elif rating in [Rating.Level.HATED, Rating.Level.DISLIKED]:
            return 'negative'
        elif rating == Rating.Level.OKAY:
            return 'neutral'
        return None

    def get(self, request, username1, username2):
        user1 = get_object_or_404(User, username=username1)
        user2 = get_object_or_404(User, username=username2)

        # Get all ratings for both users (exclude NO_RATING)
        user1_ratings = {
            r.item_id: {'rating': r.rating, 'item': r.item}
            for r in Rating.objects.filter(
                user=user1
            ).exclude(
                rating=Rating.Level.NO_RATING
            ).select_related('item', 'item__category')
        }
        user2_ratings = {
            r.item_id: {'rating': r.rating, 'item': r.item}
            for r in Rating.objects.filter(
                user=user2
            ).exclude(
                rating=Rating.Level.NO_RATING
            ).select_related('item', 'item__category')
        }

        # Categorize movies by agreement type
        both_positive = []      # Both rated positively (loved/liked)
        both_negative = []      # Both rated negatively (hated/disliked)
        both_neutral = []       # Both rated neutral (okay)
        user1_positive_user2_negative = []  # user1 positive, user2 negative
        user1_negative_user2_positive = []  # user1 negative, user2 positive
        user1_positive_user2_neutral = []   # user1 positive, user2 neutral
        user1_negative_user2_neutral = []   # user1 negative, user2 neutral
        user1_neutral_user2_positive = []   # user1 neutral, user2 positive
        user1_neutral_user2_negative = []   # user1 neutral, user2 negative
        only_user1 = []         # Only user1 rated positive (for Venn diagram)
        only_user2 = []         # Only user2 rated positive (for Venn diagram)

        all_items = set(user1_ratings.keys()) | set(user2_ratings.keys())

        for item_id in all_items:
            in_user1 = item_id in user1_ratings
            in_user2 = item_id in user2_ratings

            if in_user1 and in_user2:
                r1 = user1_ratings[item_id]['rating']
                r2 = user2_ratings[item_id]['rating']
                item = user1_ratings[item_id]['item']

                cat1 = self._categorize_rating(r1)
                cat2 = self._categorize_rating(r2)

                if cat1 == cat2:
                    if cat1 == 'positive':
                        both_positive.append(item)
                    elif cat1 == 'negative':
                        both_negative.append(item)
                    elif cat1 == 'neutral':
                        both_neutral.append(item)
                else:
                    if cat1 == 'positive' and cat2 == 'negative':
                        user1_positive_user2_negative.append(item)
                    elif cat1 == 'negative' and cat2 == 'positive':
                        user1_negative_user2_positive.append(item)
                    elif cat1 == 'positive' and cat2 == 'neutral':
                        user1_positive_user2_neutral.append(item)
                    elif cat1 == 'negative' and cat2 == 'neutral':
                        user1_negative_user2_neutral.append(item)
                    elif cat1 == 'neutral' and cat2 == 'positive':
                        user1_neutral_user2_positive.append(item)
                    elif cat1 == 'neutral' and cat2 == 'negative':
                        user1_neutral_user2_negative.append(item)
            elif in_user1:
                # Only user1 rated - add to Venn only if positive
                if self._categorize_rating(user1_ratings[item_id]['rating']) == 'positive':
                    only_user1.append(user1_ratings[item_id]['item'])
            else:
                # Only user2 rated - add to Venn only if positive
                if self._categorize_rating(user2_ratings[item_id]['rating']) == 'positive':
                    only_user2.append(user2_ratings[item_id]['item'])

        # Sort all lists by title
        for lst in [both_positive, both_negative, both_neutral,
                    user1_positive_user2_negative, user1_negative_user2_positive,
                    user1_positive_user2_neutral, user1_negative_user2_neutral,
                    user1_neutral_user2_positive, user1_neutral_user2_negative,
                    only_user1, only_user2]:
            lst.sort(key=lambda x: x.title.lower())

        # Calculate compatibility
        compat = calculate_compatibility(user1, user2)

        return render(request, 'accounts/compare.html', {
            'user1': user1,
            'user2': user2,
            'compatibility': compat,
            'both_positive': both_positive,
            'both_negative': both_negative,
            'both_neutral': both_neutral,
            'user1_positive_user2_negative': user1_positive_user2_negative,
            'user1_negative_user2_positive': user1_negative_user2_positive,
            'user1_positive_user2_neutral': user1_positive_user2_neutral,
            'user1_negative_user2_neutral': user1_negative_user2_neutral,
            'user1_neutral_user2_positive': user1_neutral_user2_positive,
            'user1_neutral_user2_negative': user1_neutral_user2_negative,
            'only_user1': only_user1,
            'only_user2': only_user2,
        })


class CompareThreeUsersView(View):
    """View to compare three users' movie preferences with a 3-way Venn diagram (positive/negative/neutral)."""

    def _categorize_rating(self, rating):
        """Categorize a rating as positive, negative, or neutral."""
        if rating in [Rating.Level.LOVED, Rating.Level.LIKED]:
            return 'positive'
        elif rating in [Rating.Level.HATED, Rating.Level.DISLIKED]:
            return 'negative'
        elif rating == Rating.Level.OKAY:
            return 'neutral'
        return None

    def get(self, request, username1, username2, username3):
        user1 = get_object_or_404(User, username=username1)
        user2 = get_object_or_404(User, username=username2)
        user3 = get_object_or_404(User, username=username3)

        # Get all ratings for three users (exclude NO_RATING)
        user1_ratings = {
            r.item_id: {'rating': r.rating, 'item': r.item}
            for r in Rating.objects.filter(
                user=user1
            ).exclude(
                rating=Rating.Level.NO_RATING
            ).select_related('item', 'item__category')
        }
        user2_ratings = {
            r.item_id: {'rating': r.rating, 'item': r.item}
            for r in Rating.objects.filter(
                user=user2
            ).exclude(
                rating=Rating.Level.NO_RATING
            ).select_related('item', 'item__category')
        }
        user3_ratings = {
            r.item_id: {'rating': r.rating, 'item': r.item}
            for r in Rating.objects.filter(
                user=user3
            ).exclude(
                rating=Rating.Level.NO_RATING
            ).select_related('item', 'item__category')
        }

        # Get sets of items each user rated positively (for Venn diagram)
        user1_positive_items = {
            item_id for item_id, data in user1_ratings.items()
            if self._categorize_rating(data['rating']) == 'positive'
        }
        user2_positive_items = {
            item_id for item_id, data in user2_ratings.items()
            if self._categorize_rating(data['rating']) == 'positive'
        }
        user3_positive_items = {
            item_id for item_id, data in user3_ratings.items()
            if self._categorize_rating(data['rating']) == 'positive'
        }

        # Seven regions for 3-way Venn diagram (based on positive ratings only)
        only_user1 = []
        only_user2 = []
        only_user3 = []
        user1_and_2_venn = []  # Both rated positive, user3 didn't
        user1_and_3_venn = []  # Both rated positive, user2 didn't
        user2_and_3_venn = []  # Both rated positive, user1 didn't
        all_three_venn = []    # All three rated positive

        # Detailed breakdowns for display (all rating types)
        user1_and_2 = {'all_positive': [], 'all_negative': [], 'all_neutral': [], 'mixed': []}
        user1_and_3 = {'all_positive': [], 'all_negative': [], 'all_neutral': [], 'mixed': []}
        user2_and_3 = {'all_positive': [], 'all_negative': [], 'all_neutral': [], 'mixed': []}
        all_three = {'all_positive': [], 'all_negative': [], 'all_neutral': [], 'mixed': []}

        # Calculate Venn diagram regions (positive ratings only)
        all_positive_items = user1_positive_items | user2_positive_items | user3_positive_items

        for item_id in all_positive_items:
            in_user1 = item_id in user1_positive_items
            in_user2 = item_id in user2_positive_items
            in_user3 = item_id in user3_positive_items

            # Get the item object from whichever user has it
            if item_id in user1_ratings:
                item = user1_ratings[item_id]['item']
            elif item_id in user2_ratings:
                item = user2_ratings[item_id]['item']
            else:
                item = user3_ratings[item_id]['item']

            if in_user1 and in_user2 and in_user3:
                all_three_venn.append(item)
            elif in_user1 and in_user2:
                user1_and_2_venn.append(item)
            elif in_user1 and in_user3:
                user1_and_3_venn.append(item)
            elif in_user2 and in_user3:
                user2_and_3_venn.append(item)
            elif in_user1:
                only_user1.append(item)
            elif in_user2:
                only_user2.append(item)
            elif in_user3:
                only_user3.append(item)

        # Sort Venn lists by title
        for lst in [only_user1, only_user2, only_user3, user1_and_2_venn,
                    user1_and_3_venn, user2_and_3_venn, all_three_venn]:
            lst.sort(key=lambda x: x.title.lower())

        all_items = set(user1_ratings.keys()) | set(user2_ratings.keys()) | set(user3_ratings.keys())

        for item_id in all_items:
            in_user1 = item_id in user1_ratings
            in_user2 = item_id in user2_ratings
            in_user3 = item_id in user3_ratings

            # Determine which region this item belongs to
            if in_user1 and in_user2 and in_user3:
                # All three rated
                r1 = user1_ratings[item_id]['rating']
                r2 = user2_ratings[item_id]['rating']
                r3 = user3_ratings[item_id]['rating']
                item = user1_ratings[item_id]['item']

                cat1 = self._categorize_rating(r1)
                cat2 = self._categorize_rating(r2)
                cat3 = self._categorize_rating(r3)

                if cat1 == cat2 == cat3:
                    if cat1 == 'positive':
                        all_three['all_positive'].append(item)
                    elif cat1 == 'negative':
                        all_three['all_negative'].append(item)
                    elif cat1 == 'neutral':
                        all_three['all_neutral'].append(item)
                else:
                    all_three['mixed'].append({'item': item, 'r1': r1, 'r2': r2, 'r3': r3})

            elif in_user1 and in_user2 and not in_user3:
                # User 1 & 2 only
                r1 = user1_ratings[item_id]['rating']
                r2 = user2_ratings[item_id]['rating']
                item = user1_ratings[item_id]['item']

                cat1 = self._categorize_rating(r1)
                cat2 = self._categorize_rating(r2)

                if cat1 == cat2:
                    if cat1 == 'positive':
                        user1_and_2['all_positive'].append(item)
                    elif cat1 == 'negative':
                        user1_and_2['all_negative'].append(item)
                    elif cat1 == 'neutral':
                        user1_and_2['all_neutral'].append(item)
                else:
                    user1_and_2['mixed'].append({'item': item, 'r1': r1, 'r2': r2})

            elif in_user1 and in_user3 and not in_user2:
                # User 1 & 3 only
                r1 = user1_ratings[item_id]['rating']
                r3 = user3_ratings[item_id]['rating']
                item = user1_ratings[item_id]['item']

                cat1 = self._categorize_rating(r1)
                cat3 = self._categorize_rating(r3)

                if cat1 == cat3:
                    if cat1 == 'positive':
                        user1_and_3['all_positive'].append(item)
                    elif cat1 == 'negative':
                        user1_and_3['all_negative'].append(item)
                    elif cat1 == 'neutral':
                        user1_and_3['all_neutral'].append(item)
                else:
                    user1_and_3['mixed'].append({'item': item, 'r1': r1, 'r3': r3})

            elif in_user2 and in_user3 and not in_user1:
                # User 2 & 3 only
                r2 = user2_ratings[item_id]['rating']
                r3 = user3_ratings[item_id]['rating']
                item = user2_ratings[item_id]['item']

                cat2 = self._categorize_rating(r2)
                cat3 = self._categorize_rating(r3)

                if cat2 == cat3:
                    if cat2 == 'positive':
                        user2_and_3['all_positive'].append(item)
                    elif cat2 == 'negative':
                        user2_and_3['all_negative'].append(item)
                    elif cat2 == 'neutral':
                        user2_and_3['all_neutral'].append(item)
                else:
                    user2_and_3['mixed'].append({'item': item, 'r2': r2, 'r3': r3})

            elif in_user1 and not in_user2 and not in_user3:
                # Don't add to only_user1 here - already handled in Venn calculation
                pass
            elif in_user2 and not in_user1 and not in_user3:
                # Don't add to only_user2 here - already handled in Venn calculation
                pass
            elif in_user3 and not in_user1 and not in_user2:
                # Don't add to only_user3 here - already handled in Venn calculation
                pass

        # Sort detailed lists by title
        for region in [user1_and_2, user1_and_3, user2_and_3, all_three]:
            for category in ['all_positive', 'all_negative', 'all_neutral']:
                region[category].sort(key=lambda x: x.title.lower())
            region['mixed'].sort(key=lambda x: x['item'].title.lower())

        # Calculate statistics for detailed breakdowns
        total_all_three = (len(all_three['all_positive']) + len(all_three['all_negative']) +
                          len(all_three['all_neutral']) + len(all_three['mixed']))
        total_user1_and_2 = (len(user1_and_2['all_positive']) + len(user1_and_2['all_negative']) +
                            len(user1_and_2['all_neutral']) + len(user1_and_2['mixed']))
        total_user1_and_3 = (len(user1_and_3['all_positive']) + len(user1_and_3['all_negative']) +
                            len(user1_and_3['all_neutral']) + len(user1_and_3['mixed']))
        total_user2_and_3 = (len(user2_and_3['all_positive']) + len(user2_and_3['all_negative']) +
                            len(user2_and_3['all_neutral']) + len(user2_and_3['mixed']))

        return render(request, 'accounts/compare_three.html', {
            'user1': user1,
            'user2': user2,
            'user3': user3,
            # Venn diagram counts (positive ratings only)
            'only_user1': only_user1,
            'only_user2': only_user2,
            'only_user3': only_user3,
            'user1_and_2_venn': user1_and_2_venn,
            'user1_and_3_venn': user1_and_3_venn,
            'user2_and_3_venn': user2_and_3_venn,
            'all_three_venn': all_three_venn,
            # Detailed breakdowns (all rating types)
            'user1_and_2': user1_and_2,
            'user1_and_3': user1_and_3,
            'user2_and_3': user2_and_3,
            'all_three': all_three,
            'total_all_three': total_all_three,
            'total_user1_and_2': total_user1_and_2,
            'total_user1_and_3': total_user1_and_3,
            'total_user2_and_3': total_user2_and_3,
        })
