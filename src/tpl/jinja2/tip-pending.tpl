{% set bot = ctb.conf["reddit"]["auth"]["username"] %}
Hey {{ dummy_message.author | replace('_', '\_') }}, u/{{ source }} sent you a __{{ amount_formatted }}__ tip.

Reply with __[accept](https://www.reddit.com/message/compose?to={{ bot }}&subject=accept&message=accept)__ to claim it.

Reply with __[decline](https://www.reddit.com/message/compose?to={{ bot }}&subject=decline&message=decline)__ to decline it.

__Pending tips expire in {{ ctb.conf["misc"]["expire_pending_hours"] }} hours.__

{% set message = dummy_message %}
{% include 'footer.tpl' %}
