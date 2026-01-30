from django import forms
from .models import Item
from .imdb_utils import extract_imdb_id


class AddItemForm(forms.Form):
    """Simple form that only requires an IMDB URL to add a movie."""
    imdb_url = forms.CharField(
        label='IMDB URL',
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500',
            'placeholder': 'https://www.imdb.com/title/tt0111161/',
        })
    )

    def clean_imdb_url(self):
        url = self.cleaned_data['imdb_url']
        imdb_id = extract_imdb_id(url)
        if not imdb_id:
            raise forms.ValidationError(
                'Please enter a valid IMDB URL (e.g., https://www.imdb.com/title/tt0111161/)'
            )
        return url
