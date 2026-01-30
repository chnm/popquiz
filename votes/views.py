from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from catalog.models import Item
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
