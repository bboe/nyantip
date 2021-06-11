Hey {{ dummy_message.author | replace('_', '\_') }}, you have received a __{{ amount_formatted }}__ tip from u/{{ source }}.

Curious what a Nyancoin is and how you can use it? Check out <{{ ctb.conf["reddit"]["help"] }}> :3

{% set message = dummy_message %}
{% include 'footer.tpl' %}
