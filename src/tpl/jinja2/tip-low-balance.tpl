I'm sorry {{ message.author | replace('_', '\_') }}, your balance of __{{ balance_formatted }}__ is insufficient to complete this {{ action_name }} requiring __{{ balance_needed_formatted }}__.
{% if action_name == "withdraw" %}

Withdrawals are subject to network confirmations and network fees. {{ ctb.conf["coin"]["name"] }} requires {{ ctb.conf["coin"]["minconf"]["withdraw"] }} confirmations and a {{ "%.6g" % ctb.conf["coin"]["txfee"] }} fee.

If the balance above doesn't match your reported tip balance, try waiting for more network confirmations.

>**Tip:** To withdraw everything, use the `all` keyword - `withdraw ADDRESS all` - and I'll automatically deduct the required network fee.
{% endif %}

{% include 'footer.tpl' %}
