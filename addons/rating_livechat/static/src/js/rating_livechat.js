
(function() {

    "use strict";

    var _t = openerp._t;
    var rating_livechat = {};
    openerp.rating_livechat = rating_livechat;


    /* Rating livechat object */
    rating_livechat.Feedback = openerp.Widget.extend({
        template : "rating_livechat.feedback",
        init: function(parent){
            this._super(parent);
            this.conversation = parent;
            this.reason = false;
            this.rating = false;
        },
        start: function(){
            this._super.apply(this.arguments);
            // bind events
            this.$('.oe_rating_livechat_choices img').on('click', _.bind(this.click_smiley, this));
            this.$('.oe_rating_livechat_reason_button #submit').on('click', _.bind(this.click_send, this));
        },
        click_smiley: function(ev){
            this.rating = parseInt($(ev.currentTarget).data('value'));
            this.$('.oe_rating_livechat_choices img').removeClass('selected');
            this.$('.oe_rating_livechat_choices img[data-value="'+this.rating+'"]').addClass('selected');
            // only display textearea if bad smiley selected
            if(this.rating == 0){
                this.$('.oe_rating_livechat_reason').show();
            }else{
                this.$('.oe_rating_livechat_reason').hide();
            }
            this.$('textarea').val(''); // empty the reason each time a click on a smiley is done
        },
        click_send: function(ev){
            this.reason = this.$('textarea').val();
            if(_.contains([0,5,10], this.rating)){ // need to use contains, since the rating can 0, evaluate to false
                this._send_feedback();
            }
        },
        _send_feedback: function(){
            var self = this;
            var uuid = this.conversation.get('session').uuid;
            openerp.session.rpc("/rating/livechat/feedback", {uuid: uuid, rate: this.rating, reason : this.reason}).then(function(res) {
                self.trigger("feedback_sent"); // will close the conversation
            });
        }
    });

    openerp.im_livechat.LiveSupport.include({
        _get_template_list: function(){
            var templates = this._super.apply(this, arguments);
            templates.push('/rating_livechat/static/src/xml/rating_livechat.xml');
            return templates;
        },
    });

    openerp.im_chat.Conversation.include({
        init: function(){
            this._super.apply(this, arguments);
            this.feedback = false;
        },
        click_close: function(event) {
            if(!this.feedback && (this.get('messages').length > 1)){
                this.feedback = new rating_livechat.Feedback(this);
                this.$(".oe_im_chatview_content").empty();
                this.feedback.appendTo( this.$(".oe_im_chatview_content"));
                // bind event to close conversation
                this.feedback.on("feedback_sent", this, this.click_close);
            }else{
                this._super.apply(this, arguments);
            }
        },
    });

    return rating_livechat;

})();
