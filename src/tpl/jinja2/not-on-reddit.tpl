I'm sorry {{ message.author | replace('_', '\_') }}, your tip has failed because user **{{ destination | replace('_', '\_') }}** is not on Reddit.

{% include 'footer.tpl' %}
