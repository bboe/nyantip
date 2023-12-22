Hey u/{{ dummy_message.author }}, you have received a __{{ amount_formatted }}__ tip from u/{{ source }}.

Curious what a {{ config["coin"]["name"] }} is and how you can use it? Check out the [help]({{ "/r/{}/wiki/{}".format(config["reddit"]["subreddit"], "index") }}).

{% set message = dummy_message %}
{% include 'footer.tpl' %}
