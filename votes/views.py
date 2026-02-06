from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db.models import Count

from catalog.models import Item, Category, Song, SongUpvote
from .models import Vote


@login_required
@require_POST
def vote_view(request):
    item_id = request.POST.get('item_id')
    choice = request.POST.get('choice')

    if not item_id or choice not in [c[0] for c in Vote.Choice.choices]:
        return redirect('home')

    item = get_object_or_404(Item, id=item_id)

    vote, created = Vote.objects.update_or_create(
        user=request.user,
        item=item,
        defaults={'choice': choice}
    )

    # Check for custom redirect
    next_url = request.POST.get('next')
    if next_url:
        return redirect(next_url)

    return redirect('category_detail', slug=item.category.slug)


@login_required
@require_POST
def vote_api(request):
    """API endpoint for voting that returns JSON with next item."""
    item_id = request.POST.get('item_id')
    choice = request.POST.get('choice')
    category_slug = request.POST.get('category_slug')

    if not item_id or choice not in [c[0] for c in Vote.Choice.choices]:
        return JsonResponse({'error': 'Invalid vote data'}, status=400)

    item = get_object_or_404(Item, id=item_id)
    category = get_object_or_404(Category, slug=category_slug)

    # Save the vote
    vote, created = Vote.objects.update_or_create(
        user=request.user,
        item=item,
        defaults={'choice': choice}
    )

    # Get items user has already voted on
    voted_item_ids = Vote.objects.filter(
        user=request.user,
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

    current_item = unvoted_items.first()
    remaining_count = unvoted_items.count()
    total_count = Item.objects.filter(category=category).count()
    voted_count = total_count - remaining_count

    if current_item:
        return JsonResponse({
            'success': True,
            'current_item': {
                'id': current_item.id,
                'title': current_item.title,
                'year': current_item.year,
                'poster_url': current_item.poster_url,
                'imdb_url': current_item.imdb_url,
            },
            'remaining_count': remaining_count,
            'voted_count': voted_count,
            'total_count': total_count,
        })
    else:
        return JsonResponse({
            'success': True,
            'completed': True,
            'voted_count': voted_count,
            'total_count': total_count,
        })


@login_required
@require_POST
def song_upvote_api(request):
    """API endpoint for toggling song upvotes."""
    song_id = request.POST.get('song_id')

    if not song_id:
        return JsonResponse({'error': 'Missing song_id'}, status=400)

    song = get_object_or_404(Song, id=song_id)

    # Toggle upvote: if exists, remove it; if not, add it
    upvote = SongUpvote.objects.filter(user=request.user, song=song).first()

    if upvote:
        # Remove upvote
        upvote.delete()
        upvoted = False
    else:
        # Add upvote
        SongUpvote.objects.create(user=request.user, song=song)
        upvoted = True

    # Get updated upvote count
    upvote_count = SongUpvote.objects.filter(song=song).count()

    return JsonResponse({
        'success': True,
        'upvoted': upvoted,
        'upvote_count': upvote_count,
    })
