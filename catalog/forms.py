from django import forms
from .models import Item, Song
from .imdb_utils import extract_imdb_id
from .tmdb_utils import extract_tmdb_id
from .musicbrainz_utils import extract_musicbrainz_id, extract_musicbrainz_release_id


class AddItemForm(forms.Form):
    """Form to add a movie/TV series (via IMDB or TMDB), artist, or release (via MusicBrainz)."""
    url = forms.CharField(
        label='URL',
        max_length=500,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500',
            'placeholder': 'IMDB or TMDB URL',
        })
    )

    def __init__(self, *args, category=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.category = category

        if category:
            if category.item_label == 'artist':
                self.fields['url'].widget.attrs['placeholder'] = 'https://musicbrainz.org/artist/...'
                self.fields['url'].label = 'MusicBrainz Artist URL'
            elif category.item_label == 'release':
                self.fields['url'].widget.attrs['placeholder'] = 'https://musicbrainz.org/release-group/...'
                self.fields['url'].label = 'MusicBrainz Release URL'
            else:
                self.fields['url'].widget.attrs['placeholder'] = (
                    'https://www.imdb.com/title/tt0111161/  or  '
                    'https://www.themoviedb.org/movie/550'
                )
                self.fields['url'].label = 'IMDB or TMDB URL'

    def clean_url(self):
        url = self.cleaned_data['url'].strip()
        category = self.category

        if category and category.item_label == 'artist':
            if not extract_musicbrainz_id(url):
                raise forms.ValidationError(
                    'Please enter a valid MusicBrainz artist URL '
                    '(e.g., https://musicbrainz.org/artist/...)'
                )
        elif category and category.item_label == 'release':
            if not extract_musicbrainz_release_id(url):
                raise forms.ValidationError(
                    'Please enter a valid MusicBrainz release-group URL '
                    '(e.g., https://musicbrainz.org/release-group/...)'
                )
        else:
            # Accept either IMDB or TMDB URLs
            is_imdb = bool(extract_imdb_id(url))
            tmdb_id, _ = extract_tmdb_id(url)
            is_tmdb = tmdb_id is not None
            if not is_imdb and not is_tmdb:
                raise forms.ValidationError(
                    'Please enter a valid IMDB URL (e.g., https://www.imdb.com/title/tt0111161/) '
                    'or TMDB URL (e.g., https://www.themoviedb.org/movie/550).'
                )

        return url


class AddSongForm(forms.ModelForm):
    """Form to manually add a song to an artist."""
    class Meta:
        model = Song
        fields = ['title', 'album', 'year']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-pink-500',
                'placeholder': 'Song title',
            }),
            'album': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-pink-500',
                'placeholder': 'Album name (optional)',
            }),
            'year': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-pink-500',
                'placeholder': 'Release year (optional)',
                'min': 1900,
                'max': 2100,
            }),
        }
