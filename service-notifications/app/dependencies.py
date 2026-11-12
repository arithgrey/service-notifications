from app.services.slack import SlackNotifier


def get_notifier() -> SlackNotifier:
    return SlackNotifier()
