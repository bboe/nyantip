{% set bot = config["reddit"]["username"] %}
Hey u/{{ dummy_message.author }}, u/{{ source }} sent you a __{{ amount_formatted }}__ tip.

Reply with __[accept](/message/compose?to={{ bot }}&subject=accept&message=accept)__ to claim it.

Reply with __[decline](/message/compose?to={{ bot }}&subject=decline&message=decline)__ to decline it.

__Pending tips expire in {{ config["pending_hours"] }} hours.__

{% set message = dummy_message %}
{% include 'footer.tpl' %}
