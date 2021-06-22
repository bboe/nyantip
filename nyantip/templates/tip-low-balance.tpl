I'm sorry u/{{ message.author }}, your balance of __{{ balance_formatted }}__ is insufficient to complete this {{ action_name }} requiring __{{ balance_needed_formatted }}__.

{% if action_name == "withdraw" %}
Withdrawals are subject to network confirmations and network fees. {{ config["coin"]["name"] }} requires {{ config["coin"]["minconf"]["withdraw"] }} confirmations and a {{ "{:.6g}".format(config["coin"]["transaction_fee"]) }} fee.

If the balance above doesn't match your reported tip balance, try waiting for more network confirmations.

>**Tip:** To withdraw everything, use the `all` keyword - `withdraw ADDRESS all` - and I'll automatically deduct the required network fee.
{% endif %}

{% include 'footer.tpl' %}
