from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db.models import Count

from catalog.models import Item, Category
from .models import Rating


@login_required
@require_POST
def rate_view(request):
    """Submit a rating for an item (traditional form submission)."""
    item_id = request.POST.get('item_id')
    rating_value = request.POST.get('rating')

    if not item_id or rating_value not in [choice[0] for choice in Rating.Level.choices]:
        return redirect('home')

    item = get_object_or_404(Item, id=item_id)

    rating, created = Rating.objects.update_or_create(
        user=request.user,
        item=item,
        defaults={'rating': rating_value}
    )

    # Check for custom redirect
    next_url = request.POST.get('next')
    if next_url:
        return redirect(next_url)

    return redirect('category_detail', slug=item.category.slug)


@login_required
@require_POST
def rate_api(request):
    """API endpoint for rating that returns JSON with next item."""
    item_id = request.POST.get('item_id')
    rating_value = request.POST.get('rating')
    category_slug = request.POST.get('category_slug')

    if not item_id or rating_value not in [choice[0] for choice in Rating.Level.choices]:
        return JsonResponse({'error': 'Invalid rating data'}, status=400)

    item = get_object_or_404(Item, id=item_id)
    category = get_object_or_404(Category, slug=category_slug)

    # Save the rating
    rating, created = Rating.objects.update_or_create(
        user=request.user,
        item=item,
        defaults={'rating': rating_value}
    )

    # Get items user has already rated
    rated_item_ids = Rating.objects.filter(
        user=request.user,
        item__category=category
    ).values_list('item_id', flat=True)

    # Get unrated items, ordered by total rating count (most popular first)
    unrated_items = Item.objects.filter(
        category=category
    ).exclude(
        id__in=rated_item_ids
    ).annotate(
        rating_count=Count('ratings')
    ).order_by('-rating_count', 'title')

    current_item = unrated_items.first()
    remaining_count = unrated_items.count()
    total_count = Item.objects.filter(category=category).count()
    rated_count = total_count - remaining_count

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
            'rated_count': rated_count,
            'total_count': total_count,
        })
    else:
        return JsonResponse({
            'success': True,
            'completed': True,
            'rated_count': rated_count,
            'total_count': total_count,
        })
