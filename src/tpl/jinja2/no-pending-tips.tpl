I'm sorry {{ message.author | replace('_', '\_') }}, you don't have any pending tips. Perhaps they've already been confirmed, or already expired. Tips are auto-confirmed after you've registered.

{% include 'footer.tpl' %}
