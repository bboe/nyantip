{% set wiki_url = "/r/{}/wiki/index".format(config["reddit"]["subreddit"]) %}
Sorry u/{{ message.author }}, I didn't understand your {{ message_type }}. Please [verify syntax]({{ wiki_url }}) and try again.

{% include 'footer.tpl' %}
