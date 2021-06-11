{% set user_bot = ctb.conf["reddit"]["auth"]["username"] %}
I'm sorry {{ message.author | replace('_', '\_') }}, we've never met. Please __[register](https://www.reddit.com/message/compose?to={{ user_bot }}&subject=register&message=register)__ first!

{% include 'footer.tpl' %}
