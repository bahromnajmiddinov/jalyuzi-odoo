from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db.models import Q 

User = get_user_model() 

@shared_task
def send_monthly_payment_reminders():
    current_time = timezone.now()

    # Define the threshold for when a reminder is due (e.g., 30 days)
    reminder_interval_days = 30
    due_threshold = current_time - timedelta(days=reminder_interval_days)

    # 1. Find users who have NEVER received a reminder and joined long enough ago
    #    This ensures their FIRST reminder is sent after their first 30 days.
    users_for_first_reminder = User.objects.filter(
        last_reminder_sent_at__isnull=True,
        date_joined__lte=due_threshold
    )

    # 2. Find users who HAVE received a reminder, and it's been at least 30 days
    #    since their last reminder was sent.
    users_for_subsequent_reminders = User.objects.filter(
        last_reminder_sent_at__isnull=False,
        last_reminder_sent_at__lte=due_threshold
    )

    # Combine the querysets (distinct ensures no duplicates if a user somehow fits both)
    users_to_remind = (users_for_first_reminder | users_for_subsequent_reminders).distinct()

    if not users_to_remind.exists():
        print("No users due for a monthly payment reminder.")
        return

    channel_layer = get_channel_layer()

    updated_users_ids = []

    for user in users_to_remind:
        try:
            message_text = "Your monthly bill is due. Please make the payment."
            async_to_sync(channel_layer.group_send)(
                f"user_{user.id}", # Assuming you have a consumer grouped by user ID
                {
                    "type": "send_notification", # Use a specific type for clarity in consumer
                    "message": message_text,
                }
            )
            # If the send was successful, update last_reminder_sent_at
            user.last_reminder_sent_at = current_time
            updated_users_ids.append(user.id)
            print(f"Reminder sent to user: {user.email or user.username} (ID: {user.id})")

        except Exception as e:
            # Log the error for this specific user
            print(f"Error sending reminder to user {user.id}: {e}")

    # Bulk update last_reminder_sent_at to minimize DB writes
    if updated_users_ids:
        User.objects.filter(id__in=updated_users_ids).update(last_reminder_sent_at=current_time)
        print(f"Updated last_reminder_sent_at for {len(updated_users_ids)} users.")

    print("Monthly payment reminders task completed.")
    