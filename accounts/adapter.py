from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom adapter to populate user data from social providers."""

    def populate_user(self, request, sociallogin, data):
        """Populate user instance with data from social provider."""
        user = super().populate_user(request, sociallogin, data)

        # Get extra data from the social account
        extra_data = sociallogin.account.extra_data

        # Populate first_name and last_name from Slack data
        if sociallogin.account.provider == 'slack':
            user.first_name = extra_data.get('given_name', '')
            user.last_name = extra_data.get('family_name', '')
            # Get the avatar URL (use the 192px version for good quality)
            user.avatar_url = extra_data.get('https://slack.com/user_image_192',
                                            extra_data.get('picture', ''))

        return user

    def save_user(self, request, sociallogin, form=None):
        """Save user with populated data."""
        user = super().save_user(request, sociallogin, form)

        # Update avatar URL if not already set
        if not user.avatar_url and sociallogin.account.provider == 'slack':
            extra_data = sociallogin.account.extra_data
            user.avatar_url = extra_data.get('https://slack.com/user_image_192',
                                            extra_data.get('picture', ''))
            user.save()

        return user
