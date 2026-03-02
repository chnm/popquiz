import json
import random

import logging
from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, TemplateView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse
from django.db.models import Count, Q, Case, When, IntegerField, Value

from accounts.models import User
from .models import Category, Item, Song, SongUpvote
from .forms import AddItemForm, AddSongForm
from django.conf import settings as django_settings
from .imdb_utils import fetch_movie_data, extract_imdb_id, download_poster
from .tmdb_utils import search_people, fetch_director_filmography_tmdb, fetch_actor_filmography_tmdb, fetch_movie_details_tmdb, extract_tmdb_id, fetch_tv_details_tmdb

from .musicbrainz_utils import fetch_artist_data, extract_musicbrainz_id, fetch_release_data, extract_musicbrainz_release_id, search_artists, search_release_groups, search_recordings, fetch_release_tracks
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
            music_categories_with_progress = []
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
                    image_local_url='', image_source_url=''
                ).order_by('?')[:5]

                entry = {
                    'category': category,
                    'total': total_items,
                    'voted': responded_count,
                    'remaining': remaining,
                    'progress_percent': progress_percent,
                    'random_posters': random_posters,
                }
                if category.item_label in ('artist', 'release'):
                    music_categories_with_progress.append(entry)
                else:
                    categories_with_progress.append(entry)

            context['categories_with_progress'] = categories_with_progress
            context['music_categories_with_progress'] = music_categories_with_progress

            # Compute combined music progress for the unified dashboard card
            if music_categories_with_progress:
                music_total = sum(e['total'] for e in music_categories_with_progress)
                music_voted = sum(e['voted'] for e in music_categories_with_progress)
                music_remaining = music_total - music_voted
                music_progress = round((music_voted / music_total) * 100) if music_total > 0 else 0
                music_posters = []
                for e in music_categories_with_progress:
                    music_posters.extend(list(e['random_posters']))
                context['music_combined'] = {
                    'total': music_total,
                    'voted': music_voted,
                    'remaining': music_remaining,
                    'progress_percent': music_progress,
                    'random_posters': music_posters[:5],
                    'categories': music_categories_with_progress,
                }
        else:
            # For logged-out users, add random posters to categories
            categories_with_posters = []
            music_categories_with_posters = []
            for category in context['categories']:
                random_posters = Item.objects.filter(
                    category=category
                ).exclude(
                    image_local_url='', image_source_url=''
                ).order_by('?')[:5]
                entry = {
                    'category': category,
                    'random_posters': random_posters,
                }
                if category.item_label in ('artist', 'release'):
                    music_categories_with_posters.append(entry)
                else:
                    categories_with_posters.append(entry)

            context['categories_with_posters'] = categories_with_posters
            context['music_categories_with_posters'] = music_categories_with_posters

            if music_categories_with_posters:
                music_posters = []
                music_item_count = 0
                for e in music_categories_with_posters:
                    music_posters.extend(list(e['random_posters']))
                    music_item_count += e['category'].item_count
                context['music_combined_logged_out'] = {
                    'item_count': music_item_count,
                    'random_posters': music_posters[:5],
                    'categories': music_categories_with_posters,
                }

        # Get featured items for carousel - guarantee at least one per category
        base_featured_qs = Item.objects.exclude(
            image_local_url='', image_source_url=''
        ).annotate(
            loved_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.LOVED)),
            liked_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.LIKED)),
            okay_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.OKAY)),
            disliked_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.DISLIKED)),
            hated_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.HATED)),
            total_ratings=Count('ratings', filter=~Q(ratings__rating=Rating.Level.NO_RATING))
        ).filter(
            total_ratings__gt=0
        )

        # Pick one random item per category first
        seen_ids = set()
        guaranteed = []
        for cat in Category.objects.all():
            cat_item = base_featured_qs.filter(category=cat).order_by('?').first()
            if cat_item and cat_item.id not in seen_ids:
                guaranteed.append(cat_item)
                seen_ids.add(cat_item.id)

        # Fill remaining slots up to 10 with random items from any category
        remaining = max(0, 10 - len(guaranteed))
        if remaining > 0:
            extra = list(base_featured_qs.exclude(id__in=seen_ids).order_by('?')[:remaining])
            guaranteed.extend(extra)

        random.shuffle(guaranteed)

        featured_items = []
        for item in guaranteed:
            total = item.total_ratings
            if total > 0:
                item.loved_percent = round((item.loved_count / total) * 100)
                item.liked_percent = round((item.liked_count / total) * 100)
                item.okay_percent = round((item.okay_count / total) * 100)
                item.disliked_percent = round((item.disliked_count / total) * 100)
                item.hated_percent = round((item.hated_count / total) * 100)
            else:
                item.loved_percent = 0
                item.liked_percent = 0
                item.okay_percent = 0
                item.disliked_percent = 0
                item.hated_percent = 0
            featured_items.append(item)

        context['featured_items'] = featured_items

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
                    'review': rating.review,
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
            activities = activities[:30]

            # Mark each rating activity with whether the current user has rated that item
            rating_item_ids = {a['item'].id for a in activities if a['type'] == 'rating'}
            user_rated_ids = set(
                Rating.objects.filter(
                    user=self.request.user,
                    item_id__in=rating_item_ids
                ).exclude(rating=Rating.Level.NO_RATING).values_list('item_id', flat=True)
            )
            for activity in activities:
                if activity['type'] == 'rating':
                    activity['user_has_rated'] = activity['item'].id in user_rated_ids
                else:
                    activity['user_has_rated'] = True  # additions always visible

            # Limit to 30 most recent activities (client-side pagination shows 6 per page)
            context['recent_activities'] = activities

            # Get featured reviews (ratings with non-empty reviews, random selection)
            featured_reviews = list(
                Rating.objects.exclude(review='').select_related(
                    'user', 'item', 'item__category'
                ).order_by('?')[:12]
            )
            review_item_ids = {r.item_id for r in featured_reviews}
            user_rated_review_ids = set(
                Rating.objects.filter(
                    user=self.request.user,
                    item_id__in=review_item_ids
                ).exclude(rating=Rating.Level.NO_RATING).values_list('item_id', flat=True)
            )
            for review in featured_reviews:
                review.user_has_rated = review.item_id in user_rated_review_ids
            context['featured_reviews'] = featured_reviews

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
                'rating': ratings_dict.get(item.id, None)  # None = never rated (distinct from no_rating/"Haven't Seen")
            })

        # Sort: Loved, Liked, Okay, Disliked, Hated, Never Rated, Haven't Seen
        rating_order = {
            Rating.Level.LOVED: 0,
            Rating.Level.LIKED: 1,
            Rating.Level.OKAY: 2,
            Rating.Level.DISLIKED: 3,
            Rating.Level.HATED: 4,
            Rating.Level.NO_RATING: 5, # explicitly marked "Haven't Seen"
            None: 6,                   # never rated — appears last
        }
        items_with_ratings.sort(key=lambda x: (rating_order.get(x['rating'], 5), x['item'].title.lower()))

        context['items_with_ratings'] = items_with_ratings
        context['item_count'] = items.count()
        return context


# Maps each category slug to the IMDB title types that belong in it.
# Used to prevent adding a TV series to Movies (and vice versa).
CATEGORY_ALLOWED_IMDB_TYPES = {
    'movies': {'Movie', 'TVMovie'},
    'tv-series': {'TVSeries', 'TVMiniSeries'},
}

# Human-readable labels for IMDB title types used in error messages.
IMDB_TYPE_LABELS = {
    'Movie': 'movie',
    'TVMovie': 'TV movie',
    'TVSeries': 'TV series',
    'TVMiniSeries': 'TV mini-series',
    'TVEpisode': 'TV episode',
}


class AddItemView(LoginRequiredMixin, View):
    """View to add an item (movie, TV series, or artist) using an IMDB or MusicBrainz URL."""

    def get(self, request, slug):
        category = get_object_or_404(Category, slug=slug)
        form = AddItemForm(category=category)
        return render(request, 'catalog/add_item.html', {
            'form': form,
            'category': category,
        })

    def post(self, request, slug):
        category = get_object_or_404(Category, slug=slug)
        form = AddItemForm(request.POST, category=category)

        if form.is_valid():
            url = form.cleaned_data['url']

            if category.item_label == 'artist':
                return self._handle_musicbrainz(request, form, category, slug, url)
            elif category.item_label == 'release':
                return self._handle_musicbrainz_release(request, form, category, slug, url)
            else:
                return self._handle_imdb(request, form, category, slug, url)

        return render(request, 'catalog/add_item.html', {
            'form': form,
            'category': category,
        })

    def _handle_imdb(self, request, form, category, slug, url):
        """Handle adding an item via IMDB or TMDB URL."""
        from django.conf import settings as _settings
        api_key = _settings.TMDB_API_KEY

        # Detect whether this is a TMDB URL
        tmdb_id, tmdb_media_type = extract_tmdb_id(url)

        if tmdb_id is not None:
            # --- TMDB path ---
            if tmdb_media_type == 'tv':
                movie_data = fetch_tv_details_tmdb(tmdb_id, api_key)
            else:
                movie_data = fetch_movie_details_tmdb(tmdb_id, api_key)
                # fetch_movie_details_tmdb requires an IMDB id, but we can still
                # proceed if the movie has no IMDB id — just skip that field.
                if movie_data and not movie_data.get('imdb_id'):
                    movie_data['imdb_id'] = None

            if not movie_data:
                form.add_error('url', 'Could not fetch data from TMDB. Please check the URL and try again.')
                return render(request, 'catalog/add_item.html', {
                    'form': form,
                    'category': category,
                })
        else:
            # --- IMDB path (original behaviour) ---
            movie_data = fetch_movie_data(url)
            if not movie_data:
                form.add_error(
                    'url',
                    'Could not fetch data from IMDB. '
                    'Try using a TMDB link instead (https://www.themoviedb.org).'
                )
                return render(request, 'catalog/add_item.html', {
                    'form': form,
                    'category': category,
                })

        # Check for duplicate by IMDB ID (if available)
        imdb_id = movie_data.get('imdb_id') or None
        if imdb_id:
            existing = Item.objects.filter(imdb_id=imdb_id).first()
            if existing:
                form.add_error('url', f'This {category.item_label} already exists: "{existing.title}"')
                return render(request, 'catalog/add_item.html', {
                    'form': form,
                    'category': category,
                })

        # Validate that the title type matches this category
        title_type = movie_data.get('title_type')
        allowed_types = CATEGORY_ALLOWED_IMDB_TYPES.get(category.slug)
        if allowed_types and title_type and title_type not in allowed_types:
            friendly_type = IMDB_TYPE_LABELS.get(title_type, title_type)
            form.add_error(
                'url',
                f'That link is for a {friendly_type}, not a {category.item_label}. '
                f'Please add it to the correct category.'
            )
            return render(request, 'catalog/add_item.html', {
                'form': form,
                'category': category,
            })

        # Download poster image locally
        raw_source = movie_data.get('image_source_url') or ''
        poster_key = imdb_id or str(tmdb_id or 'unknown')
        local_image = download_poster(raw_source, poster_key) if raw_source else None

        # Create the item
        item = Item.objects.create(
            category=category,
            title=movie_data['title'],
            year=movie_data.get('year'),
            years_running=movie_data.get('years_running') or '',
            director=movie_data.get('director') or '',
            genre=movie_data.get('genre') or '',
            imdb_id=imdb_id or None,
            imdb_url=movie_data.get('imdb_url') or '',
            image_source_url=raw_source,
            image_local_url=local_image or '',
            added_by=request.user,
        )

        messages.success(request, f'"{item.title}" has been added!')
        return redirect('category_detail', slug=slug)

    def _handle_musicbrainz(self, request, form, category, slug, url):
        """Handle adding an artist via MusicBrainz URL."""
        data = fetch_artist_data(url, fetch_songs=True, max_songs=50)

        if not data:
            form.add_error('url', 'Could not fetch artist data from MusicBrainz. Please check the URL and try again.')
            return render(request, 'catalog/add_item.html', {
                'form': form,
                'category': category,
            })

        # Check if artist already exists
        existing = Item.objects.filter(musicbrainz_id=data['musicbrainz_id']).first()
        if existing:
            form.add_error('url', f'This artist already exists: "{existing.title}"')
            return render(request, 'catalog/add_item.html', {
                'form': form,
                'category': category,
            })

        # Create the artist item
        item = Item.objects.create(
            category=category,
            title=data['title'],
            year=None,
            musicbrainz_id=data['musicbrainz_id'],
            image_source_url=data['poster_url'] or '',
            added_by=request.user,
        )

        # Create songs if any were fetched
        songs_count = 0
        if 'songs' in data and data['songs']:
            for song_data in data['songs']:
                Song.objects.create(
                    artist=item,
                    title=song_data['title'],
                    musicbrainz_id=song_data.get('musicbrainz_id'),
                    year=song_data.get('year'),
                    album=song_data.get('album', ''),
                )
                songs_count += 1

        messages.success(request, f'"{item.title}" has been added with {songs_count} songs!')
        return redirect('category_detail', slug=slug)

    def _handle_musicbrainz_release(self, request, form, category, slug, url):
        """Handle adding a music release (album, single, EP) via MusicBrainz release-group URL."""
        data = fetch_release_data(url)

        if not data:
            form.add_error('url', 'Could not fetch release data from MusicBrainz. Please check the URL and try again.')
            return render(request, 'catalog/add_item.html', {
                'form': form,
                'category': category,
            })

        # Check if release already exists
        existing = Item.objects.filter(musicbrainz_id=data['musicbrainz_id']).first()
        if existing:
            form.add_error('url', f'This release already exists: "{existing.title}"')
            return render(request, 'catalog/add_item.html', {
                'form': form,
                'category': category,
            })

        raw_source = data.get('poster_url') or ''
        local_image = download_poster(raw_source, data['musicbrainz_id']) if raw_source else None

        item = Item.objects.create(
            category=category,
            title=data['title'],
            year=data['year'],
            director=data['artist'],  # Reuse director field to store artist name
            genre=data['release_type'],  # Reuse genre field to store release type (Album, Single, EP)
            genre_tags=data.get('genre_tags', ''),
            spotify_url=data.get('spotify_url') or '',
            musicbrainz_id=data['musicbrainz_id'],
            image_source_url=raw_source,
            image_local_url=local_image or '',
            added_by=request.user,
        )

        messages.success(request, f'"{item.title}" has been added!')
        return redirect('category_detail', slug=slug)


def _bulk_add_from_tmdb(movies, category, user, api_key):
    """
    Given a list of TMDB movie dicts (with tmdb_id/title/year), fetch details
    and add to the database.  Returns (added, skipped, failed) counts.
    """
    added_count = 0
    skipped_count = 0
    failed_count = 0

    for movie in movies:
        tmdb_id = movie['tmdb_id']

        # Fetch full details from TMDB (includes imdb_id, director, genre, poster)
        movie_data = fetch_movie_details_tmdb(tmdb_id, api_key)
        if not movie_data:
            failed_count += 1
            continue

        imdb_id = movie_data.get('imdb_id') or ''

        # Skip adult / X-rated content
        if movie_data.get('adult'):
            skipped_count += 1
            continue

        # Skip TV movies / made-for-TV productions
        genre_str = movie_data.get('genre') or ''
        if 'TV Movie' in genre_str:
            skipped_count += 1
            continue

        # Skip short films and music videos (runtime known and under 40 minutes)
        runtime = movie_data.get('runtime') or 0
        if 0 < runtime < 40:
            skipped_count += 1
            continue

        # Skip duplicates — check by IMDB ID if available
        if imdb_id and Item.objects.filter(imdb_id=imdb_id).exists():
            skipped_count += 1
            continue

        # Download poster
        raw_source = movie_data.get('image_source_url') or ''
        local_image = download_poster(raw_source, imdb_id or str(tmdb_id)) if raw_source else None

        Item.objects.create(
            category=category,
            title=movie_data['title'],
            year=movie_data.get('year'),
            years_running=movie_data.get('years_running') or '',
            director=movie_data.get('director') or '',
            genre=movie_data.get('genre') or '',
            imdb_id=imdb_id or None,
            imdb_url=movie_data.get('imdb_url') or '',
            image_source_url=raw_source,
            image_local_url=local_image or '',
            added_by=user,
        )
        added_count += 1

    return added_count, skipped_count, failed_count


def _bulk_result_message(request, person_name, category, added, skipped, failed):
    """Show appropriate flash message after a bulk add operation."""
    label = category.item_label
    if added > 0:
        messages.success(request, f'Done, I have added {added} {person_name} {label}{"s" if added != 1 else ""} to {category.name}!')
    elif skipped > 0 and failed == 0:
        messages.info(request, f'All {person_name} {label}s are already in your {category.name} collection.')
    elif failed > 0 and added == 0:
        messages.warning(request, f'Could not add any {person_name} {label}s — {failed} failed to fetch.')
    else:
        parts = []
        if added:
            parts.append(f'added {added}')
        if skipped:
            parts.append(f'skipped {skipped} (already in database)')
        if failed:
            parts.append(f'{failed} failed')
        messages.info(request, f'{person_name}: {", ".join(parts)}')


class AddByDirectorView(LoginRequiredMixin, View):
    """View to add all movies by a director using TMDB for complete filmographies."""

    def get(self, request, slug):
        category = get_object_or_404(Category, slug=slug)
        return render(request, 'catalog/add_by_director.html', {'category': category})

    def post(self, request, slug):
        category = get_object_or_404(Category, slug=slug)
        api_key = django_settings.TMDB_API_KEY

        if not api_key:
            messages.error(request, 'This feature is not yet fully set up. Please check back soon.')
            return render(request, 'catalog/add_by_director.html', {'category': category})

        if 'tmdb_person_id' in request.POST:
            return self._add_movies(request, category, slug, api_key)

        director_name = request.POST.get('director_name', '').strip()
        if not director_name:
            messages.error(request, 'Please enter a director name.')
            return render(request, 'catalog/add_by_director.html', {'category': category})

        search_results = search_people(director_name, api_key)
        if not search_results:
            messages.error(request, f'No directors found matching "{director_name}". Please check the spelling and try again.')
            return render(request, 'catalog/add_by_director.html', {
                'category': category, 'director_name': director_name,
            })

        if len(search_results) == 1:
            return self._add_movies(request, category, slug, api_key, tmdb_person_id=search_results[0]['tmdb_id'])

        return render(request, 'catalog/add_by_director.html', {
            'category': category,
            'director_name': director_name,
            'search_results': search_results,
        })

    def _add_movies(self, request, category, slug, api_key, tmdb_person_id=None):
        if tmdb_person_id is None:
            try:
                tmdb_person_id = int(request.POST.get('tmdb_person_id', ''))
            except (ValueError, TypeError):
                messages.error(request, 'No director selected.')
                return redirect('add_by_director', slug=slug)

        filmography = fetch_director_filmography_tmdb(tmdb_person_id, api_key)
        if not filmography:
            messages.error(request, 'Could not fetch filmography. Please try again.')
            return redirect('add_by_director', slug=slug)

        person_name = filmography['name']
        movies = filmography['movies']
        if not movies:
            messages.warning(request, f'No {category.item_label}s found for {person_name}.')
            return redirect('add_by_director', slug=slug)

        added_count, skipped_count, failed_count = _bulk_add_from_tmdb(
            movies, category, request.user, api_key
        )
        _bulk_result_message(request, person_name, category, added_count, skipped_count, failed_count)
        return redirect('category_detail', slug=slug)


class AddByActorView(LoginRequiredMixin, View):
    """View to add all movies starring an actor using TMDB for complete filmographies."""

    def get(self, request, slug):
        category = get_object_or_404(Category, slug=slug)
        return render(request, 'catalog/add_by_actor.html', {'category': category})

    def post(self, request, slug):
        category = get_object_or_404(Category, slug=slug)
        api_key = django_settings.TMDB_API_KEY

        if not api_key:
            messages.error(request, 'This feature is not yet fully set up. Please check back soon.')
            return render(request, 'catalog/add_by_actor.html', {'category': category})

        if 'tmdb_person_id' in request.POST:
            return self._add_movies(request, category, slug, api_key)

        actor_name = request.POST.get('actor_name', '').strip()
        if not actor_name:
            messages.error(request, 'Please enter an actor name.')
            return render(request, 'catalog/add_by_actor.html', {'category': category})

        search_results = search_people(actor_name, api_key)
        if not search_results:
            messages.error(request, f'No actors found matching "{actor_name}". Please check the spelling and try again.')
            return render(request, 'catalog/add_by_actor.html', {
                'category': category, 'actor_name': actor_name,
            })

        if len(search_results) == 1:
            return self._add_movies(request, category, slug, api_key, tmdb_person_id=search_results[0]['tmdb_id'])

        return render(request, 'catalog/add_by_actor.html', {
            'category': category,
            'actor_name': actor_name,
            'search_results': search_results,
        })

    def _add_movies(self, request, category, slug, api_key, tmdb_person_id=None):
        if tmdb_person_id is None:
            try:
                tmdb_person_id = int(request.POST.get('tmdb_person_id', ''))
            except (ValueError, TypeError):
                messages.error(request, 'No actor selected.')
                return redirect('add_by_actor', slug=slug)

        filmography = fetch_actor_filmography_tmdb(tmdb_person_id, api_key)
        if not filmography:
            messages.error(request, 'Could not fetch filmography. Please try again.')
            return redirect('add_by_actor', slug=slug)

        person_name = filmography['name']
        movies = filmography['movies']
        if not movies:
            messages.warning(request, f'No {category.item_label}s found for {person_name}.')
            return redirect('add_by_actor', slug=slug)

        added_count, skipped_count, failed_count = _bulk_add_from_tmdb(
            movies, category, request.user, api_key
        )
        _bulk_result_message(request, person_name, category, added_count, skipped_count, failed_count)
        return redirect('category_detail', slug=slug)


class AddMusicSearchView(LoginRequiredMixin, View):
    """Search MusicBrainz by name and let the user pick the right artist or release to add."""

    def get(self, request, slug):
        category = get_object_or_404(Category, slug=slug)
        return render(request, 'catalog/add_music_search.html', {'category': category})

    def post(self, request, slug):
        category = get_object_or_404(Category, slug=slug)

        # Step 2: user selected a result from the list
        if 'musicbrainz_id' in request.POST:
            mb_id = request.POST.get('musicbrainz_id', '').strip()
            return self._add_by_id(request, category, slug, mb_id)

        # Step 1: search by name
        query = request.POST.get('query', '').strip()
        if not query:
            messages.error(request, 'Please enter a name to search.')
            return render(request, 'catalog/add_music_search.html', {'category': category})

        if category.item_label == 'artist':
            results = search_artists(query)
        else:
            results = search_release_groups(query)

        if not results:
            messages.error(request, f'No results found for "{query}". Try a different spelling.')
            return render(request, 'catalog/add_music_search.html', {
                'category': category,
                'query': query,
            })

        # Single result — add immediately without making the user click
        if len(results) == 1:
            return self._add_by_id(request, category, slug, results[0]['musicbrainz_id'])

        return render(request, 'catalog/add_music_search.html', {
            'category': category,
            'query': query,
            'search_results': results,
        })

    def _add_by_id(self, request, category, slug, mb_id):
        if category.item_label == 'artist':
            existing = Item.objects.filter(musicbrainz_id=mb_id).first()
            if existing:
                messages.info(request, f'"{existing.title}" is already in {category.name}.')
                return redirect('category_detail', slug=slug)

            data = fetch_artist_data(mb_id, fetch_songs=True, max_songs=50)
            if not data:
                messages.error(request, 'Could not fetch artist data from MusicBrainz. Please try again.')
                return redirect('add_music_search', slug=slug)

            item = Item.objects.create(
                category=category,
                title=data['title'],
                musicbrainz_id=data['musicbrainz_id'],
                image_source_url=data.get('poster_url') or '',
                added_by=request.user,
            )
            songs_count = 0
            for song_data in data.get('songs', []):
                Song.objects.create(
                    artist=item,
                    title=song_data['title'],
                    musicbrainz_id=song_data.get('musicbrainz_id'),
                    year=song_data.get('year'),
                    album=song_data.get('album', ''),
                )
                songs_count += 1
            messages.success(request, f'"{item.title}" has been added with {songs_count} songs!')

        else:  # release
            existing = Item.objects.filter(musicbrainz_id=mb_id).first()
            if existing:
                messages.info(request, f'"{existing.title}" is already in {category.name}.')
                return redirect('category_detail', slug=slug)

            data = fetch_release_data(mb_id)
            if not data:
                messages.error(request, 'Could not fetch release data from MusicBrainz. Please try again.')
                return redirect('add_music_search', slug=slug)

            raw_source = data.get('poster_url') or ''
            local_image = download_poster(raw_source, data['musicbrainz_id']) if raw_source else None

            item = Item.objects.create(
                category=category,
                title=data['title'],
                year=data['year'],
                director=data['artist'],
                genre=data['release_type'],
                genre_tags=data.get('genre_tags', ''),
                spotify_url=data.get('spotify_url') or '',
                musicbrainz_id=data['musicbrainz_id'],
                image_source_url=raw_source,
                image_local_url=local_image or '',
                added_by=request.user,
            )
            messages.success(request, f'"{item.title}" has been added!')

        return redirect('category_detail', slug=slug)


logger = logging.getLogger(__name__)


class AddMusicView(LoginRequiredMixin, View):
    """Unified music search: find artists, releases, and songs in one interface."""

    def get(self, request):
        return render(request, 'catalog/add_music.html')

    def post(self, request):
        # Step 2: user selected a result
        selected_id = request.POST.get('selected_id', '').strip()
        if selected_id:
            return self._handle_selection(request, selected_id)

        # Step 1: search by name
        query = request.POST.get('query', '').strip()
        if not query:
            messages.error(request, 'Please enter a name to search.')
            return render(request, 'catalog/add_music.html')

        artist_results = search_artists(query, limit=5)
        release_results = search_release_groups(query, limit=5)
        recording_results = search_recordings(query, limit=5)

        if not artist_results and not release_results and not recording_results:
            messages.error(request, f'No results found for "{query}". Try a different spelling.')
            return render(request, 'catalog/add_music.html', {'query': query})

        return render(request, 'catalog/add_music.html', {
            'query': query,
            'artist_results': artist_results,
            'release_results': release_results,
            'recording_results': recording_results,
        })

    def _handle_selection(self, request, selected_id):
        parts = selected_id.split(':')
        sel_type = parts[0]

        try:
            if sel_type == 'artist' and len(parts) >= 2:
                return self._add_artist(request, parts[1])
            elif sel_type == 'release' and len(parts) >= 2:
                return self._add_release(request, parts[1])
            elif sel_type == 'recording' and len(parts) >= 2:
                rec_id = parts[1]
                artist_id = parts[2] if len(parts) > 2 else None
                rg_id = parts[3] if len(parts) > 3 else None
                return self._add_recording(request, rec_id, artist_id, rg_id)
        except Exception:
            logger.exception('Error adding music item')
            messages.error(request, 'Something went wrong. Please try again.')
            return redirect('add_music')

        messages.error(request, 'Invalid selection.')
        return redirect('add_music')

    def _get_artists_category(self):
        return Category.objects.get(slug='music-artists')

    def _get_releases_category(self):
        return Category.objects.get(slug='music-releases')

    def _find_or_create_artist(self, request, artist_mb_id):
        """Find an existing artist Item or create one from MusicBrainz data."""
        existing = Item.objects.filter(musicbrainz_id=artist_mb_id).first()
        if existing:
            return existing

        data = fetch_artist_data(artist_mb_id, fetch_songs=False)
        if not data:
            return None

        item = Item.objects.create(
            category=self._get_artists_category(),
            title=data['title'],
            musicbrainz_id=data['musicbrainz_id'],
            image_source_url=data.get('poster_url') or '',
            added_by=request.user,
        )
        return item

    def _find_or_create_release(self, request, rg_mb_id):
        """Find an existing release Item or create one from MusicBrainz data."""
        existing = Item.objects.filter(musicbrainz_id=rg_mb_id).first()
        if existing:
            return existing

        data = fetch_release_data(rg_mb_id)
        if not data:
            return None

        raw_source = data.get('poster_url') or ''
        local_image = download_poster(raw_source, data['musicbrainz_id']) if raw_source else None

        item = Item.objects.create(
            category=self._get_releases_category(),
            title=data['title'],
            year=data['year'],
            director=data['artist'],
            genre=data['release_type'],
            genre_tags=data.get('genre_tags', ''),
            spotify_url=data.get('spotify_url') or '',
            musicbrainz_id=data['musicbrainz_id'],
            image_source_url=raw_source,
            image_local_url=local_image or '',
            added_by=request.user,
        )
        return item, data

    @transaction.atomic
    def _add_artist(self, request, mb_id):
        """Add an artist only (no releases or songs)."""
        existing = Item.objects.filter(musicbrainz_id=mb_id).first()
        if existing:
            messages.info(request, f'"{existing.title}" is already added.')
            return redirect('item_detail', category_slug=existing.category.slug, item_id=existing.id)

        data = fetch_artist_data(mb_id, fetch_songs=False)
        if not data:
            messages.error(request, 'Could not fetch artist data from MusicBrainz. Please try again.')
            return redirect('add_music')

        artists_cat = self._get_artists_category()
        item = Item.objects.create(
            category=artists_cat,
            title=data['title'],
            musicbrainz_id=data['musicbrainz_id'],
            image_source_url=data.get('poster_url') or '',
            added_by=request.user,
        )
        messages.success(request, f'"{item.title}" has been added!')
        return redirect('item_detail', category_slug=artists_cat.slug, item_id=item.id)

    @transaction.atomic
    def _add_release(self, request, mb_id):
        """Add a release, its artist, and all tracks."""
        existing = Item.objects.filter(musicbrainz_id=mb_id).first()
        if existing:
            messages.info(request, f'"{existing.title}" is already added.')
            return redirect('item_detail', category_slug=existing.category.slug, item_id=existing.id)

        data = fetch_release_data(mb_id)
        if not data:
            messages.error(request, 'Could not fetch release data from MusicBrainz. Please try again.')
            return redirect('add_music')

        # Find or create the artist
        artist_item = None
        artist_id = data.get('artist_id')
        if artist_id:
            artist_item = self._find_or_create_artist(request, artist_id)

        # Create the release
        releases_cat = self._get_releases_category()
        raw_source = data.get('poster_url') or ''
        local_image = download_poster(raw_source, data['musicbrainz_id']) if raw_source else None

        release_item = Item.objects.create(
            category=releases_cat,
            title=data['title'],
            year=data['year'],
            director=data['artist'],
            genre=data['release_type'],
            genre_tags=data.get('genre_tags', ''),
            spotify_url=data.get('spotify_url') or '',
            musicbrainz_id=data['musicbrainz_id'],
            image_source_url=raw_source,
            image_local_url=local_image or '',
            added_by=request.user,
        )

        # Fetch and create tracks
        tracks = fetch_release_tracks(mb_id)
        songs_count = 0
        if artist_item and tracks:
            for track in tracks:
                rec_id = track.get('musicbrainz_id')
                if rec_id and Song.objects.filter(musicbrainz_id=rec_id).exists():
                    # Link existing song to this release if not already linked
                    existing_song = Song.objects.filter(musicbrainz_id=rec_id).first()
                    if not existing_song.release:
                        existing_song.release = release_item
                        existing_song.save(update_fields=['release'])
                    continue
                Song.objects.create(
                    artist=artist_item,
                    release=release_item,
                    title=track['title'],
                    musicbrainz_id=rec_id,
                    album=data['title'],
                )
                songs_count += 1

        parts = [f'"{release_item.title}" has been added']
        if artist_item:
            parts.append(f'with artist "{artist_item.title}"')
        if songs_count:
            parts.append(f'and {songs_count} tracks')
        messages.success(request, ' '.join(parts) + '!')
        return redirect('item_detail', category_slug=releases_cat.slug, item_id=release_item.id)

    @transaction.atomic
    def _add_recording(self, request, rec_id, artist_id, rg_id):
        """Add a single song, plus its artist and release if not yet added."""
        # Check if this exact recording already exists as a Song
        existing_song = Song.objects.filter(musicbrainz_id=rec_id).first()
        if existing_song:
            messages.info(request, f'"{existing_song.title}" is already added.')
            return redirect('item_detail', category_slug=existing_song.artist.category.slug, item_id=existing_song.artist.id)

        # We need the recording title from the POST data
        rec_title = request.POST.get('rec_title', '').strip()
        rec_album = request.POST.get('rec_album', '').strip()

        # Find or create the artist
        artist_item = None
        if artist_id:
            artist_item = self._find_or_create_artist(request, artist_id)

        if not artist_item:
            messages.error(request, 'Could not determine the artist for this recording.')
            return redirect('add_music')

        # Find or create the release
        release_item = None
        if rg_id:
            existing_release = Item.objects.filter(musicbrainz_id=rg_id).first()
            if existing_release:
                release_item = existing_release
            else:
                release_data = fetch_release_data(rg_id)
                if release_data:
                    releases_cat = self._get_releases_category()
                    raw_source = release_data.get('poster_url') or ''
                    local_image = download_poster(raw_source, release_data['musicbrainz_id']) if raw_source else None
                    release_item = Item.objects.create(
                        category=releases_cat,
                        title=release_data['title'],
                        year=release_data['year'],
                        director=release_data['artist'],
                        genre=release_data['release_type'],
                        genre_tags=release_data.get('genre_tags', ''),
                        spotify_url=release_data.get('spotify_url') or '',
                        musicbrainz_id=release_data['musicbrainz_id'],
                        image_source_url=raw_source,
                        image_local_url=local_image or '',
                        added_by=request.user,
                    )

        # Create the song
        song = Song.objects.create(
            artist=artist_item,
            release=release_item,
            title=rec_title or 'Unknown',
            musicbrainz_id=rec_id,
            album=rec_album,
        )

        parts = [f'Song "{song.title}" has been added']
        if release_item:
            parts.append(f'from "{release_item.title}"')
        parts.append(f'by {artist_item.title}')
        messages.success(request, ' '.join(parts) + '!')
        return redirect('item_detail', category_slug=artist_item.category.slug, item_id=artist_item.id)


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
        context['all_categories'] = Category.objects.all()
        context['url_name'] = 'stats'

        return context


class DecadeStatsView(TemplateView):
    """View showing movies/songs ranked by decade."""
    template_name = 'catalog/decades.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = get_object_or_404(Category, slug=self.kwargs['slug'])
        context['category'] = category

        # Check if this is a music category
        is_music = 'music' in category.slug.lower() or 'artist' in category.slug.lower()
        context['is_music'] = is_music

        if is_music:
            self._build_music_decades(context, category)
        else:
            self._build_item_decades(context, category)

        context['all_categories'] = Category.objects.all()
        context['url_name'] = 'decades'
        return context

    def _build_music_decades(self, context, category):
        """Build decade stats for music categories (songs grouped by decade)."""
        songs = Song.objects.filter(artist__category=category).prefetch_related('upvotes')

        decades = {}
        no_year = []

        for song in songs:
            upvote_count = song.upvotes.count()
            song_data = {
                'song': song,
                'upvote_count': upvote_count,
            }

            if song.year:
                decade = (song.year // 10) * 10
                if decade not in decades:
                    decades[decade] = []
                decades[decade].append(song_data)
            else:
                no_year.append(song_data)

        # Sort songs within each decade by upvote count
        for decade in decades:
            decades[decade].sort(key=lambda x: (-x['upvote_count'], x['song'].title.lower()))

        sorted_decades = sorted(decades.items(), key=lambda x: -x[0])

        context['decades'] = sorted_decades
        context['no_year'] = no_year

    def _build_item_decades(self, context, category):
        """Build decade stats for non-music categories (items with ratings)."""
        items = Item.objects.filter(category=category).annotate(
            loved_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.LOVED)),
            liked_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.LIKED)),
            okay_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.OKAY)),
            disliked_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.DISLIKED)),
            hated_count=Count('ratings', filter=Q(ratings__rating=Rating.Level.HATED)),
        )

        decades = {}
        no_year = []

        for item in items:
            total_ratings = (item.loved_count + item.liked_count + item.okay_count +
                           item.disliked_count + item.hated_count)

            if total_ratings > 0:
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

        for decade in decades:
            decades[decade].sort(key=lambda x: (
                x['score'] is None,
                -(x['score'] or 0),
                -x['loved_count'],
                x['item'].title.lower()
            ))

        sorted_decades = sorted(decades.items(), key=lambda x: -x[0])

        context['decades'] = sorted_decades
        context['no_year'] = no_year


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
        context['all_categories'] = Category.objects.all()
        context['url_name'] = 'eclectic'

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
        context['all_categories'] = Category.objects.all()
        context['url_name'] = 'divisive'

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

        # Check if this is an artist or release (music categories)
        is_artist = category.item_label == 'artist'
        is_release = category.item_label == 'release'
        context['is_artist'] = is_artist
        context['is_release'] = is_release

        # Get current user's rating if authenticated
        user_rating = None
        if self.request.user.is_authenticated:
            try:
                user_rating = Rating.objects.get(item=item, user=self.request.user)
                context['user_rating'] = user_rating.rating
                context['user_review'] = user_rating.review
            except Rating.DoesNotExist:
                context['user_rating'] = Rating.Level.NO_RATING
                context['user_review'] = ''

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

        # Reviews with text, sorted by reviewer last name
        reviews_with_text = [r for r in all_ratings if r.review]
        reviews_with_text.sort(key=lambda r: (r.user.last_name.lower(), r.user.first_name.lower()))
        context['reviews_with_text'] = reviews_with_text

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

        # If this is a release, get its tracklist with upvote data, ordered by insertion order (= track order)
        if is_release:
            tracks = Song.objects.filter(release=item).prefetch_related('upvotes__user').order_by('id')
            tracklist = []
            for song in tracks:
                upvotes = list(song.upvotes.all())
                user_upvoted = any(u.user == self.request.user for u in upvotes) if self.request.user.is_authenticated else False
                tracklist.append({
                    'song': song,
                    'upvote_count': len(upvotes),
                    'user_upvoted': user_upvoted,
                })
            context['tracklist'] = tracklist

        # If this is an artist, get songs with upvote data
        if is_artist:
            songs = Song.objects.filter(artist=item).prefetch_related('upvotes__user')

            songs_with_upvotes = []
            for song in songs:
                upvotes = list(song.upvotes.all())
                user_upvoted = any(u.user == self.request.user for u in upvotes) if self.request.user.is_authenticated else False

                songs_with_upvotes.append({
                    'song': song,
                    'upvote_count': len(upvotes),
                    'user_upvoted': user_upvoted,
                    'upvoted_by': [u.user for u in upvotes],
                })

            # Sort by upvote count (most upvoted first)
            songs_with_upvotes.sort(key=lambda x: (-x['upvote_count'], x['song'].title.lower()))

            context['songs'] = songs_with_upvotes

        return context


class AddSongView(LoginRequiredMixin, View):
    """View to manually add a song to an artist."""

    def get(self, request, category_slug, item_id):
        category = get_object_or_404(Category, slug=category_slug)
        artist = get_object_or_404(Item, id=item_id, category=category)
        form = AddSongForm()
        return render(request, 'catalog/add_song.html', {
            'form': form,
            'category': category,
            'artist': artist,
        })

    def post(self, request, category_slug, item_id):
        category = get_object_or_404(Category, slug=category_slug)
        artist = get_object_or_404(Item, id=item_id, category=category)
        form = AddSongForm(request.POST)

        if form.is_valid():
            song = form.save(commit=False)
            song.artist = artist
            song.save()

            messages.success(request, f'"{song.title}" has been added!')
            return redirect('item_detail', category_slug=category_slug, item_id=item_id)

        return render(request, 'catalog/add_song.html', {
            'form': form,
            'category': category,
            'artist': artist,
        })
