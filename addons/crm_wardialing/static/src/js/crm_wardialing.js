
openerp.crm_wardialing = function(instance) {

    var _t = openerp._t;
    var _lt = openerp._lt;
    var QWeb = openerp.qweb;
    var crm_wardialing = openerp.crm_wardialing = {};  
    
    crm_wardialing.PhonecallWidget = openerp.Widget.extend({
        "template": "crm_wardialing.PhonecallWidget",
        events: {
            "click": "select_call",
        },
        init: function(parent, phonecall, image_small, email) {
            this._super(parent);
            this.set("id", phonecall.id);
            if(phonecall.partner_name){
                this.set("partner", phonecall.partner_name);
            }else{
                this.set("partner", "Unknown");
            }
            

            if(phonecall.description){
                this.set("description", phonecall.description);
            }else{
                this.set("description", "There is no description");
            }
            
            if(phonecall.opportunity_id){
                this.set("opportunity", phonecall.opportunity_name);
                this.set("opportunity_id", phonecall.opportunity_id);
            }else{
                this.set("opportunity", "No opportunity linked");
            }
            this.set("image_small", image_small);
            this.set("email", email);
            if(phonecall.opportunity_name.length < 24){
                this.set("opportunity", phonecall.opportunity_name);
            }else{
                var opportunity = phonecall.opportunity_name.substring(0,23) + '...';
                this.set("opportunity", opportunity);
            }             
        },
        start: function() {
            this.$el.data("phonecall", {id:this.get("id"), partner:this.get("partner")});
            this.$el.draggable({helper: "clone"});
        },

        //select the clicked call, show options and put some highlight on it
        select_call: function(){
            this.trigger("select_call", this)
        },
    });
    
    crm_wardialing.DialingPanel = openerp.Widget.extend({
        template: "crm_wardialing.DialingPanel",
        events: {
            "keyup .oe_dial_searchbox": "input_change",
            "click .oe_dial_callbutton": "call_button",
            "click .oe_dial_hangupbutton": "hangup_button",
            "click .oe_dial_changelog": "change_log",
            "click .oe_dial_email": "send_email",
            "click .oe_dial_to_client": "to_client",
            "click .oe_dial_to_lead": "to_lead",
            "click .oe_dial_transferbutton": "transfer_button",
            "click .oe_dial_nextcallbutton": "nextCall_button",
        },

        init: function(parent) {    
            this._super(parent);
            this.shown = false;
            this.set("current_search", "");
            this.phonecalls = {};
            this.widgets = {};
            this.formatCurrency;
            this.phonecall_channel;
            this.buttonAnimated = false;
        },

        start: function() {
            var self = this;
            //this.ari_client = new openerp.ari_client();
            //this.ari_client.init();
            try{
                this.sip_js = new openerp.sip_js();
                this.sip_js.init();
            }catch(e){
                console.log(e);
            }
            
            //To get the formatCurrency function from the server
            new instance.web.Model("res.currency")
                .call("get_format_currencies_js_function")
                .then(function(data) {
                    self.formatCurrency = new Function("amount, currency_id", data);
                    //update of the pannel's list
                    
                    self.search_phonecalls_status();
                });
            this.$el.css("bottom", -this.$el.outerHeight());
            openerp.web.bus.on('reload_panel', this, this.search_phonecalls_status);
            return;
        },

        //Modify the phonecalls list when the search input changes
        input_change: function() {
            var self = this;
            _.each(this.phonecalls,function(phonecall){
                if(phonecall.partner_name.toLowerCase().indexOf(this.$(".oe_dial_searchbox").val().toLowerCase()) == -1 
                    && phonecall.opportunity_name.toLowerCase().indexOf(this.$(".oe_dial_searchbox").val().toLowerCase()) == -1){
                    self.$el.find(".phonecall_id:contains(" + phonecall.id+ ")").parent().parent().hide();
                }else{
                    self.$el.find(".phonecall_id:contains(" + phonecall.id+ ")").parent().parent().show();
                }
            });
        },

        //Get the phonecalls and create the widget to put inside the panel
        search_phonecalls_status: function() {
            var phonecall_model = new openerp.web.Model("crm.phonecall");
            var self = this;

            new openerp.web.Model("crm.phonecall").call("get_list",[this.get("current_search")]).then(function(result){
                var old_widgets = self.widgets;                   
                self.widgets = {};
                self.phonecalls = {};

                $(".oe_dial_callbutton").attr('disabled','disabled');
                $(".oe_dial_inCallButton").attr('disabled','disabled');
                if(result.phonecalls.length > 0){
                    $(".oe_dial_callbutton").removeAttr('disabled');
                }
                self.$el.find(".oe_dial_content").animate({
                    bottom: 0,
                });
                _.each(result.phonecalls, function(phonecall){     
                    var widget = new openerp.crm_wardialing.PhonecallWidget(self, phonecall,phonecall.partner_image_small, phonecall.partner_email);
                    widget.appendTo(self.$(".oe_dial_phonecalls"));
                    
                    widget.on("select_call", self, self.select_call);
                    self.widgets[phonecall.id] = widget;
                    
                    if(phonecall.partner_name){
                        if(! phonecall.partner_title){
                            var partner_name = phonecall.partner_name;
                        }else{
                            var partner_name = phonecall.partner_title + ' ' + phonecall.partner_name;
                        }
                    }else{
                        var partner_name = "Unknown";
                    }
                    var empty_star = parseInt(phonecall.max_priority) - parseInt(phonecall.opportunity_priority);
                    $("[rel='popover']").popover({
                        placement : 'right', // top, bottom, left or right
                        title : QWeb.render("crm_wardialing_Tooltip_title", {
                            opportunity: phonecall.opportunity_name, priority: parseInt(phonecall.opportunity_priority), empty_star:empty_star}), 
                        html: 'true', 
                        content :  QWeb.render("crm_wardialing_Tooltip",{
                            partner_name: partner_name,
                            phone: phonecall.partner_phone,
                            mobile: phonecall.partner_mobile,
                            description: phonecall.description,
                            email: phonecall.partner_email,
                            title_action: phonecall.opportunity_title_action,
                            planned_revenue: self.formatCurrency(phonecall.opportunity_planned_revenue, phonecall.opportunity_company_currency),
                            probability: phonecall.opportunity_probability
                        }),
                    });
                    self.phonecalls[phonecall.id] = phonecall;
                });    
                _.each(old_widgets, function(w) {
                    w.destroy();
                });
            });
            
        },

        //function that will display the panel
        switch_display: function() {
            if (this.shown) {
                this.$el.animate({
                    bottom: -this.$el.outerHeight(),
                });
            } else {
                // update the list of user status when show the dialer panel
                this.search_phonecalls_status();

                this.$el.animate({
                    bottom: 0,
                });
            }
            this.shown = ! this.shown;
        },

        //action to change the main view to go to the opportunity's view
        to_lead: function() {
            var id = this.$el.find(".oe_dial_selected_phonecall").find(".phonecall_id").text();
            var phonecall = this.phonecalls[id];
            //Call of the function xmlid_to_res_model_res_id to get the id of the opportunity's form view and not the lead's form view
            new instance.web.Model("ir.model.data").call("xmlid_to_res_model_res_id",["crm.crm_case_form_view_oppor"]).then(function(data){
                openerp.client.action_manager.do_action({
                    type: 'ir.actions.act_window',
                    res_model: "crm.lead",
                    res_id: phonecall.opportunity_id,
                    views: [[data[1], 'form']],
                    target: 'current',
                    context: {},
                    flags: {initial_mode: "edit",},
                });
            })
            
        },

        //action to change the main view to go to the client's view
        to_client: function() {
            var id = this.$el.find(".oe_dial_selected_phonecall").find(".phonecall_id").text();
            var phonecall = this.phonecalls[id];
            
            openerp.client.action_manager.do_action({
                type: 'ir.actions.act_window',
                res_model: "res.partner",
                res_id: phonecall.partner_id,
                views: [[false, 'form']],
                target: 'current',
                context: {},
                flags: {initial_mode: "edit",},
            });
        },

        //action to select a call and display the specific actions
        select_call: function(phonecall_widget){
            if(!this.buttonAnimated){
                var self = this;
                this.buttonAnimated = true;
                var classes = phonecall_widget.$()[0].className.split(" ");
                self.$(".oe_dial_selected_phonecall").removeClass("oe_dial_selected_phonecall");
                if(classes.indexOf("oe_dial_selected_phonecall") == -1){
                    phonecall_widget.$()[0].className += " oe_dial_selected_phonecall";
                    console.log(this.buttonAnimated);
                    this.$el.find(".oe_dial_phonecalls").animate({
                        height: (this.$el.find(".oe_dial_phonecalls").height() - this.$el.find(".oe_dial_optionalbuttons").outerHeight()),
                    }, 500,function(){
                        self.buttonAnimated = false;
                    });
                    this.$el.find(".oe_dial_email").css("display","none");
                    if(phonecall_widget.get('email')){
                        this.$el.find(".oe_dial_email").css("display","inline");
                        this.$el.find(".oe_dial_changelog").css("width", "44%");
                    }else{
                        this.$el.find(".oe_dial_changelog").css("width", "90%");
                    }
                }else{
                    this.$el.find(".oe_dial_phonecalls").animate({
                        height: (this.$el.find(".oe_dial_phonecalls").height() + this.$el.find(".oe_dial_optionalbuttons").outerHeight()),
                    }, 500,function(){
                        self.buttonAnimated = false;
                    });
                }
            } 
        },

        //action done when the button "call" is clicked
        call_button: function(){
            
            var phonecall_model = new openerp.web.Model("crm.phonecall");
            var self = this;
            if(this.$el.find(".oe_dial_selected_phonecall").find(".phonecall_id").text() != ''){
                var phonecall_id = this.$el.find(".oe_dial_selected_phonecall").find(".phonecall_id").text();
                phonecall_model.call("init_call", [this.phonecalls[phonecall_id].id]);
                /*
                //JS Ari lib
                this.ari_client.call(this.phonecalls[phonecall_id],function(channel){
                    console.log("after the call")
                    self.phonecall_channel = channel;
                    console.log(self.phonecall_channel);
                });
                */
                this.sip_js.call(this.phonecalls[phonecall_id]);
            }else{
                var phonecall_id = this.$el.find(".oe_dial_phonecalls > div:first-child").find(".phonecall_id").text();
                if(phonecall_id){
                    phonecall_model.call("init_call", [this.phonecalls[phonecall_id].id]);
                    /*
                    //JS Ari lib
                    this.ari_client.call(this.phonecalls[phonecall_id],function(channel){
                        console.log("after the call")
                        self.phonecall_channel = channel;
                    });
                    */
                    this.sip_js.call(this.phonecalls[phonecall_id]);
                }
            }
        },

        //action done when the button "Hang Up" is clicked
        hangup_button: function(){
            this.sip_js.hangup();
            /*
            var phonecall_model = new openerp.web.Model("crm.phonecall");
            if(this.$el.find(".oe_dial_selected_phonecall").find(".phonecall_id").text() != ''){
                var phonecall_id = this.$el.find(".oe_dial_selected_phonecall").find(".phonecall_id").text();
                phonecall_model.call("hangup_call", [this.phonecalls[phonecall_id].id]).then(function(phonecall){
                    openerp.web.bus.trigger('reload_panel');
                });
                //this.ari_client.hangup(this.phonecall_channel);
                this.sip_js.hangup();
            }else if(this.$el.find(".oe_dial_phonecalls > div:first-child").find(".phonecall_id").text()){
                var phonecall_id = this.$el.find(".oe_dial_phonecalls > div:first-child").find(".phonecall_id").text();
                phonecall_model.call("hangup_call", [this.phonecalls[phonecall_id].id]).then(function(phonecall){
                    openerp.web.bus.trigger('reload_panel');
                });
                //this.ari_client.hangup(this.phonecall_channel);
                this.sip_js.hangup();
            }*/
        },

        //action done when the button "Transfer" is clicked
        transfer_button: function(){
            //TODO Add a test to see if in call or not. Add transfer option (which extension, external phone...)
            this.sip_js.transfer();
        },

        //action done when the button "Next Call" is clicked
        nextCall_button: function(){
            /* TODO open the wizard to log the call or not when the current call is hanged up before calling the next client ? 
            var phonecall_model = new openerp.web.Model("crm.phonecall");
            var self = this;
            if(this.$el.find(".oe_dial_selected_phonecall").find(".phonecall_id").text() != ''){
                var phonecall_id = this.$el.find(".oe_dial_phonecalls > div:first-child").find(".phonecall_id").text();
                phonecall_model.call("init_call", [this.phonecalls[phonecall_id].id]);
                this.sip_js.call(this.phonecalls[phonecall_id]);
            }else{
                var phonecall_id = this.$el.find(".oe_dial_phonecalls > div:first-child").find(".phonecall_id").text();
                if(phonecall_id){
                    phonecall_model.call("init_call", [this.phonecalls[phonecall_id].id]);

                    this.sip_js.call(this.phonecalls[phonecall_id]);
                }
            }*/
        },

        //action done when the button "Call Log" is clicked
        change_log: function(){
            var id = this.$el.find(".oe_dial_selected_phonecall").find(".phonecall_id").text();
            var self = this;
            openerp.client.action_manager.do_action({
                type: 'ir.actions.act_window',
                key2: 'client_action_multi',
                src_model: "crm.phonecall",
                res_model: "crm.phonecall.log.wizard",
                multi: "True",
                target: 'new',
                context: {'phonecall_id': id, 'phonecall' : this.phonecalls[id]},
                views: [[false, 'form']],
            });
        },

        //action done when the button "Send Email" is clicked
        send_email: function(){
            var id = this.$el.find(".oe_dial_selected_phonecall").find(".phonecall_id").text();
            var widget = this.widgets[this.phonecalls[id].id];
            var self = this;
            openerp.client.action_manager.do_action({
                type: 'ir.actions.act_window',
                res_model: 'mail.compose.message',
                src_model: 'crm.phonecall',
                multi: "True",
                target: 'new',
                key2: 'client_action_multi',
                context: {
                            'default_composition_mode': 'comment',
                            'default_email_to': widget.get('email'),
                            'default_model': 'crm.lead',
                            'default_res_id': this.phonecalls[id].opportunity_id,
                            'default_partner_ids': [this.phonecalls[id].partner_id],
                        },
                views: [[false, 'form']],
            });
        },
    });
    
    //Creation of the panel and binding of the display with the button in the top bar
    if(openerp.web && openerp.web.UserMenu) {
        openerp.web.UserMenu.include({
            do_update: function(){
                var self = this;
                if($('.oe_systray .oe_topbar_dialbutton_icon')){
                    self.update_promise.then(function() {
                        var dial = new openerp.crm_wardialing.DialingPanel(self);
                        dial.appendTo(openerp.client.$el);
                        $('.oe_topbar_dialbutton_icon').parent().on("click", dial, _.bind(dial.switch_display, dial));
                        
                        //bind the action to retrieve the panel with the button in the header of the panel
                        $('.oe_dial_close_icon').parent().on("click", dial, _.bind(dial.switch_display, dial));

                        //bind the action to refresh the panel information
                        $('.oe_dial_search_icon').parent().on("click", dial, _.bind(dial.search_phonecalls_status, dial));

                        //bind the action to refresh the panel information
                        $('.oe_dial_refresh_icon').parent().on("click", dial, _.bind(dial.search_phonecalls_status, dial));
                    });
                }
                return this._super.apply(this, arguments);
            },
        });
    }
    
    //Trigger "reload_panel" that will be catch by the widget to reload the panel
    openerp.crm_wardialing.reload_panel = function () {
        openerp.web.bus.trigger('reload_panel');
        //Return an action to close the wizard after the reload of the panel
        return { type: 'ir.actions.act_window_close' };
    }
    instance.web.client_actions.add("reload_panel", "openerp.crm_wardialing.reload_panel");
    
    return crm_wardialing;
};