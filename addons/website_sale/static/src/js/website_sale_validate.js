$(document).ready(function () {

    var _poll_nbr = 0;

    function payment_transaction_poll_status() {
        var order_node = $('div.oe_website_sale_tx_status');
        if (! order_node || order_node.data('orderId') === undefined) {
            return;
        }
        var order_id = order_node.data('orderId');
        return openerp.jsonRpc('/shop/payment/get_status/' + order_id, 'call', {
        }).then(function (result) {
            var tx_node = $('div.oe_website_sale_tx_status');
            _poll_nbr += 1;
            if (result[1].state == 'pending' && result[1].validation == 'automatic' && _poll_nbr <= 5) {
                tx_node.html(result[0]);
                setTimeout(function () {
                    payment_transaction_poll_status();
                }, 1000);
            }
            else {
                tx_node.html(result[0]);
            }
        });
    }

    payment_transaction_poll_status();
});
