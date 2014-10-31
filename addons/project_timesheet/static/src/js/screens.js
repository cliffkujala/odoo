function odoo_project_timesheet_screens(project_timesheet) {

    var QWeb = openerp.qweb,
    _t = openerp._t;

    //Move it in lib code, may be in openerpframework.js
    $.fn.openerpClass = function(additionalClass) {
        // This plugin should be applied on top level elements
        additionalClass = additionalClass || '';
        if (!!$.browser.msie) {
            additionalClass += ' openerp_ie';
        }
        return this.each(function() {
            $(this).addClass('openerp ' + additionalClass);
        });
    };

    var messages_by_seconds = function() {
        return [
            [0, _t("Loading...")],
            [20, _t("Still loading...")],
            [60, _t("Still loading...<br />Please be patient.")],
            [120, _t("Don't leave yet,<br />it's still loading...")],
            [300, _t("You may not believe it,<br />but the application is actually loading...")],
            [420, _t("Take a minute to get a coffee,<br />because it's loading...")],
            [3600, _t("Maybe you should consider reloading the application by pressing F5...")]
        ];
    };

    //Block UI Stuff
    project_timesheet.Throbber = openerp.Widget.extend({
        template: "Throbber",
        start: function() {
            var opts = {
              lines: 13, // The number of lines to draw
              length: 7, // The length of each line
              width: 4, // The line thickness
              radius: 10, // The radius of the inner circle
              rotate: 0, // The rotation offset
              color: '#FFF', // #rgb or #rrggbb
              speed: 1, // Rounds per second
              trail: 60, // Afterglow percentage
              shadow: false, // Whether to render a shadow
              hwaccel: false, // Whether to use hardware acceleration
              className: 'spinner', // The CSS class to assign to the spinner
              zIndex: 2e9, // The z-index (defaults to 2000000000)
              top: 'auto', // Top position relative to parent in px
              left: 'auto' // Left position relative to parent in px
            };
            this.spin = new Spinner(opts).spin(this.$el[0]);
            this.start_time = new Date().getTime();
            this.act_message();
        },
        act_message: function() {
            var self = this;
            setTimeout(function() {
                if (self.isDestroyed())
                    return;
                var seconds = (new Date().getTime() - self.start_time) / 1000;
                var mes;
                _.each(messages_by_seconds(), function(el) {
                    if (seconds >= el[0])
                        mes = el[1];
                });
                self.$(".oe_throbber_message").html(mes);
                self.act_message();
            }, 1000);
        },
        destroy: function() {
            if (this.spin)
                this.spin.stop();
            this._super();
        },
    });
    project_timesheet.Throbber.throbbers = [];
    
    project_timesheet.blockUI = function() {
        var tmp = $.blockUI.apply($, arguments);
        var throbber = new project_timesheet.Throbber();
        project_timesheet.Throbber.throbbers.push(throbber);
        throbber.appendTo($(".oe_blockui_spin_container"));
        return tmp;
    };
    project_timesheet.unblockUI = function() {
        _.each(project_timesheet.Throbber.throbbers, function(el) {
            el.destroy();
        });
        return $.unblockUI.apply($, arguments);
    };

    var opened_modal = [];
    project_timesheet.Dialog = openerp.Widget.extend({
        //template: "ProjectTimesheetDialog",
        init: function(parent, options, content) {
            this._super();
            this.content_to_set = content;
            this.dialog_options = {
                destroy_on_close: true,
                size: 'large', //'medium', 'small'
                buttons: null,
            };
            if (options) {
                _.extend(this.dialog_options, options);
            }
            this.on("closing", this, this._closing);
            this.$buttons = $('<div class="modal-footer"><span class="oe_dialog_custom_buttons"/></div>');
        },
        renderElement: function() {
            if (this.content_to_set) {
                this.setElement(this.content_to_set);
            } else if (this.template) {
                this._super();
            }
        },
        /**
            Opens the popup. Inits the dialog if it is not already inited.
    
            @return this
        */
        open: function() {
            if (!this.dialog_inited) {
                this.init_dialog();
            }
            this.$buttons.insertAfter(this.$dialog_box.find(".modal-body"));
            $('.tooltip').remove(); //remove open tooltip if any to prevent them staying when modal is opened
            //add to list of currently opened modal
            opened_modal.push(this.$dialog_box);
            return this;
        },
        _add_buttons: function(buttons) {
            var self = this;
            var $customButons = this.$buttons.find('.oe_dialog_custom_buttons').empty();
            _.each(buttons, function(fn, text) {
                // buttons can be object or array
                var pre_text  = fn.pre_text || "";
                var post_text = fn.post_text || "";
                var oe_link_class = fn.oe_link_class;
                if (!_.isFunction(fn)) {
                    text = fn.text;
                    fn = fn.click;
                }
                var $but = $(QWeb.render('WidgetButton', { widget : { pre_text: pre_text, post_text: post_text, string: text, node: { attrs: {'class': oe_link_class} }}}));
                $customButons.append($but);
                $but.filter('button').on('click', function(ev) {
                    fn.call(self.$el, ev);
                });
            });
        },
        /**
            Initializes the popup.
    
            @return The result returned by start().
        */
        init_dialog: function() {
            var self = this;
            var options = _.extend({}, this.dialog_options);
            options.title = options.title || this.dialog_title;
            if (options.buttons) {
                this._add_buttons(options.buttons);
                delete(options.buttons);
            }
            this.renderElement();
            this.$dialog_box = $(QWeb.render('ProjectTimesheetDialog', options)).appendTo("body");
            this.$el.modal({
                'backdrop': false,
                'keyboard': true,
            });
            if (options.size !== 'large'){
                var dialog_class_size = this.$dialog_box.find('.modal-lg').removeClass('modal-lg');
                if (options.size === 'small'){
                    dialog_class_size.addClass('modal-sm');
                }
            }
    
            this.$el.appendTo(this.$dialog_box.find(".modal-body"));
            var $dialog_content = this.$dialog_box.find('.modal-content');
            if (options.dialogClass){
                $dialog_content.find(".modal-body").addClass(options.dialogClass);
            }
            $dialog_content.openerpClass();
    
            this.$dialog_box.on('hidden.bs.modal', this, function() {
                self.close();
            });
            this.$dialog_box.modal('show');
    
            this.dialog_inited = true;
            var res = this.start();
            return res;
        },
        /**
            Closes (hide) the popup, if destroy_on_close was passed to the constructor, it will be destroyed instead.
        */
        close: function(reason) {
            if (this.dialog_inited && !this.__tmp_dialog_hiding) {
                $('.tooltip').remove(); //remove open tooltip if any to prevent them staying when modal has disappeared
                if (this.$el.is(":data(bs.modal)")) {     // may have been destroyed by closing signal
                    this.__tmp_dialog_hiding = true;
                    this.$dialog_box.modal('hide');
                    this.__tmp_dialog_hiding = undefined;
                }
                this.trigger("closing", reason);
            }
        },
        _closing: function() {
            if (this.__tmp_dialog_destroying)
                return;
            if (this.dialog_options.destroy_on_close) {
                this.__tmp_dialog_closing = true;
                this.destroy();
                this.__tmp_dialog_closing = undefined;
            }
        },
        /**
            Destroys the popup, also closes it.
        */
        destroy: function (reason) {
            this.$buttons.remove();
            var self = this;
            _.each(this.getChildren(), function(el) {
                el.destroy();
            });
            if (! this.__tmp_dialog_closing) {
                this.__tmp_dialog_destroying = true;
                this.close(reason);
                this.__tmp_dialog_destroying = undefined;
            }
            if (this.dialog_inited && !this.isDestroyed() && this.$el.is(":data(bs.modal)")) {
                //we need this to put the instruction to remove modal from DOM at the end
                //of the queue, otherwise it might already have been removed before the modal-backdrop
                //is removed when pressing escape key
                var $element = this.$dialog_box;
                setTimeout(function () {
                    //remove modal from list of opened modal since we just destroy it
                    var modal_list_index = $.inArray($element, opened_modal);
                    if (modal_list_index > -1){
                        opened_modal.splice(modal_list_index,1)[0].remove();
                    }
                    if (opened_modal.length > 0){
                        //we still have other opened modal so we should focus it
                        opened_modal[opened_modal.length-1].focus();
                        //keep class modal-open (deleted by bootstrap hide fnct) on body 
                        //to allow scrolling inside the modal
                        $('body').addClass('modal-open');
                    }
                },0);
            }
            this._super();
        }
    });

    project_timesheet.ScreenSelector = openerp.Class.extend({
        init: function(options){
            this.project_timesheet_model = options.project_timesheet_model;

            this.screen_set = options.screen_set || {};

            this.default_screen = options.default_screen;

            this.current_screen = null; 

            for(screen_name in this.screen_set){
                this.screen_set[screen_name].hide();
            }

        },
        add_screen: function(screen_name, screen){
            screen.hide();
            this.screen_set[screen_name] = screen;
            return this;
        },
        set_current_screen: function(screen_name, screen_data_set, params, refresh, re_render) {
            var screen = this.screen_set[screen_name];
            if(re_render) {
                screen.renderElement();
            }
            if(!screen){
                console.error("ERROR: set_current_screen("+screen_name+") : screen not found");
            }

            var old_screen_name = this.project_timesheet_model.get_screen_data('screen');

            this.project_timesheet_model.set_screen_data('screen', screen_name);

            if(params){
                this.project_timesheet_model.set_screen_data('params', params);
            }

            if( screen_name !== old_screen_name ){
                this.project_timesheet_model.set_screen_data('previous-screen',old_screen_name);
            }

            if ( refresh || screen !== this.current_screen){
                if(this.current_screen){
                    this.current_screen.close();
                    this.current_screen.hide();
                }
                this.current_screen = screen;
                this.current_screen.show();
                if(screen_data_set && this.current_screen.set_screen_values) {
                    this.current_screen.set_screen_values(screen_data_set);
                }
            }
        },
        get_current_screen: function(){
            //return this.pos.get('selectedOrder').get_screen_data('screen') || this.default_screen;
            return this.project_timesheet_model.get_screen_data('screen') || this.default_screen;
        },
        back: function(){
            var previous = this.project_timesheet_model.get_screen_data('previous-screen');
            if(previous){
                this.set_current_screen(previous);
            }
        },
        get_current_screen_param: function(param){
            var params = this.project_timesheet_model.get_screen_data('params');
            return params ? params[param] : undefined;
        },
        set_screen_values: function() {
            //void method, child will implement if needed
        },
        set_default_screen: function(){
            this.set_current_screen(this.default_screen);
        },
    });

    project_timesheet.ScreenWidget = openerp.Widget.extend({ //Make sure we need to extend project_timesheet_widget or openerp.widget
        init: function(parent,options){
            this._super(parent,options);
            this.hidden = false;
            this.project_timesheet_model = project_timesheet.project_timesheet_model;
            this.project_timesheet_db = this.project_timesheet_model.project_timesheet_db;
        },
        // this method shows the screen and sets up all the widget related to this screen. Extend this method
        // if you want to alter the behavior of the screen.
        show: function(){
            var self = this;

            this.hidden = false;
            if(this.$el){
                this.$el.removeClass('o_hidden');
            }
        },

        // this method is called when the screen is closed to make place for a new screen. this is a good place
        // to put your cleanup stuff as it is guaranteed that for each show() there is one and only one close()
        close: function(){
            //TO Implement
        },

        // this methods hides the screen. It's not a good place to put your cleanup stuff as it is called on the
        // POS initialization.
        hide: function(){
            this.hidden = true;
            if(this.$el){
                this.$el.addClass('o_hidden');
            }
        },

        // we need this because some screens re-render themselves when they are hidden
        // (due to some events, or magic, or both...)  we must make sure they remain hidden.
        // the good solution would probably be to make them not re-render themselves when they
        // are hidden. 
        renderElement: function(){
            this._super();
            if(this.hidden){
                if(this.$el){
                    this.$el.addClass('o_hidden');
                }
            }
        },
        rpc_error: function(error) {
            if (error.data.exception_type === "except_osv" || error.data.exception_type === "warning" || error.data.exception_type === "access_error") {
                this.show_warning(error);
            } else {
                this.show_error(error);
            }
        },
        show_warning: function(error) {
            var self = this;
            if (error.data.exception_type === "except_osv") {
                error = _.extend({}, error, {data: _.extend({}, error.data, {message: error.data.arguments[0] + "\n\n" + error.data.arguments[1]})});
            }
            new project_timesheet.Dialog(this, {
                size: 'medium',
                title: "Odoo " + (_.str.capitalize(error.type) || "Warning"),
                buttons: [
                    {text: _t("Ok"), click: function() { $("body").find('.modal').modal('hide'); }}
                ],
            }, $('<div>' + QWeb.render('ProjectTimesheet.warning', {error: error}) + '</div>')).open();
        },
        show_error: function(error) {
            var self = this;
            var buttons = {};
            buttons[_t("Ok")] = function() {
                console.log("$(body).find('.modal') is ::: ",$("body").find('.modal'));
                $("body").find('.modal').modal('hide');
            };
            new project_timesheet.Dialog(this, {
                title: "Odoo " + _.str.capitalize(error.type),
                buttons: buttons
            }, QWeb.render('ProjectTimesheet.error', {widget: this, error: error})).open();
        },
    });

    project_timesheet.ActivityScreen = project_timesheet.ScreenWidget.extend({
        template: "ActivityScreen",
        init: function(project_timesheet_widget, options) {
            this._super.apply(this, arguments);
            this.project_timesheet_widget = project_timesheet_widget;
            this.activities = [];
        },
        start: function() {
            var self = this;
            this._super.apply(this, arguments);
        },
        show: function() {
            var self = this;
            this._super();
            this.activity_list = new project_timesheet.ActivityListView();
            this.activity_list.appendTo(this.$el.find(".pt_activity_body"));

            this.pad_table_to(11);
            //Add, Add Activity row prior to activities listview
            var $row = $("<tr><td><span class='pt_add_activity pt_pointer'>+ Add Activity</a></td></tr>");
            if(!this.$el.find(".pt_add_activity").length) {
                $row.prependTo(this.$el.find(".activity_row:first").parent());
            }

            this.is_available_timer_activity();
            this.$el.find(".pt_timer_button button").off("click").on("click", this.on_timer);
            //When Cancel is clicked it should move user to Activity List screen
            this.$el.find(".pt_add_activity").on("click", function() {
                self.project_timesheet_widget.screen_selector.set_current_screen("add_activity");
            });
            this.$el.find(".pt_stat").on("click", function() {
                self.project_timesheet_widget.screen_selector.set_current_screen("stat", {}, {}, false, true);
            });
            this.$el.find(".pt_sync").on("click", function() {
                self.project_timesheet_widget.screen_selector.set_current_screen("sync");
            });
            this.$el.find(".activity_row").on("click", this.on_row_click);
            this.$el.find(".pt_total").html(this.get_total());
        },
        hide: function() {
            if(this.activity_list) {
                this.activity_list.destroy();
            }
            if (this.project_m2o) {
                this.project_m2o.destroy();
            }
            if (this.task_m2o) {
                this.task_m2o.destroy();
            }
            if (this.intervalTimer) { clearInterval(this.intervalTimer);}
            this._super();
        },
        pad_table_to: function(count) {
            if (this.activity_list.activities.length >= count) {
                return;
            }
            var row = '<tr class="activity_row"><td></td></tr>';
            $rows = $(new Array(count - this.activity_list.activities.length + 1).join(row));
            if (!this.$el.find(".activity_row").length) {
                $rows.appendTo(this.$el.find(".pt_activity_body > table > tbody").parent());
            } else {
                $rows.appendTo(this.$el.find(".activity_row:last").parent());
            }
        },
        on_row_click: function(event) {
            var activity_id = $(event.currentTarget).data("activity_id");
            if(activity_id) {
                var activity = this.project_timesheet_db.get_activity_by_id(activity_id);
                //TODO: Better to develop modify screen, instead of putting static logic and putting static logic
                this.project_timesheet_widget.screen_selector.set_current_screen("add_activity", activity);
            }
        },
        get_pending_lines: function() {
            console.log("get_pending_lines are inside ActivityScreen ::: ");
            return this.project_timesheet_model.get_pending_records();
        },
        get_total: function() {
            var duration = this.activity_list.get_total().split(":");
            return _.str.sprintf("%sh %smin", duration[0], duration[1]);
        },
        get_current_UTCDate: function() {
            var d = new Date();
            return d.getUTCFullYear() +"-"+ (d.getUTCMonth()+1) +"-"+d.getUTCDate()+" "+_.str.sprintf("%02d", d.getUTCHours())+":"+_.str.sprintf("%02d", d.getUTCMinutes())+":"+_.str.sprintf("%02d", d.getUTCSeconds());//+"."+d.getUTCMilliseconds();
        },
        get_date_diff: function(new_date, old_date) {
            var difference = moment.duration(moment(new_date).diff(moment(old_date))).asHours();
            return parseFloat(difference.toFixed(2));
        },
        is_available_timer_activity: function() {
            var time_activity = this.project_timesheet_db.get_current_timer_activity();
            console.log("Inside is_available_timer_activity ::: ", time_activity);
            if (time_activity && time_activity['date']) {
                this.$el.find(".pt_timer_start,.pt_timer_stop").toggleClass("o_hidden");
                var durationObj = moment.duration(moment(this.get_current_UTCDate()).diff(moment(time_activity['date'])));
                console.log("difference is ::: ", durationObj, durationObj.asHours(), durationObj.asMinutes(), durationObj.asSeconds());
                var hours = durationObj.asHours().toString().split('.')[0],
                    minutes = (durationObj.asMinutes() % 60).toString().split(".")[0],
                    seconds = (durationObj.asSeconds() % 60).toString().split(".")[0];
                console.log("Hours, Minute and Seconds are ::: ", hours, minutes, seconds);
                this.$el.find(".pt_duration span.hours").text(hours);
                this.$el.find(".pt_duration span.minutes").text(minutes);
                this.$el.find(".pt_duration span.seconds").text(seconds);
                this.start_interval();
                this.initialize_timer();
                if (time_activity.project_id) {
                    var field_val = time_activity['project_id'];
                    this.project_m2o.set({display_string: field_val[1], value: field_val[0]});
                    this.project_m2o.display_string(field_val);
                }
                if (time_activity.task_id) {
                    var field_val = time_activity['task_id'];
                    this.task_m2o.set({display_string: field_val[1], value: field_val[0]});
                    this.task_m2o.display_string(field_val);
                }
            }
        },
        //TODO: Save timer Current time when Start Timer is clicked in localstoprage as a separate entry
        //When Activity list screen is displayed at that time read localstorage entry time and set timer value
        //Also setInterval of 1 second
        initialize_timer: function() {
            this.project_m2o = new project_timesheet.FieldMany2One(this, {model: this.project_timesheet_model , classname: "pt_input_project pt_required", label: "Select a project", id_for_input: "project_id"});
            this.project_m2o.on("change:value", this, function() {
                var project = [this.project_m2o.get("value"), this.project_m2o.get("display_string")];
                this.project_timesheet_db.set_current_timer_activity({project_id: project});
                this.task_m2o.set({display_string: false, value: false});
                this.task_m2o.display_string(false);
                this.set_project_model();
            });
            this.project_m2o.appendTo(this.$el.find(".project_m2o"));
            this.task_m2o = new project_timesheet.FieldMany2One(this, {model: false, search_model: 'task', classname: "pt_input_task", label: "Select a task", id_for_input: "task_id"});
            this.task_m2o.on("change:value", this, function() {
                var task = [this.task_m2o.get('value'), this.task_m2o.get("display_string")];
                this.project_timesheet_db.set_current_timer_activity({task_id: task});
            });
            this.task_m2o.appendTo(this.$el.find(".task_m2o"));
        },
        //Duplicate method same as Add Activity screen
        set_project_model: function() {
            var project_id = this.project_m2o.get('value');
            var projects_collection = this.project_timesheet_model.get('projects');
            var project_model = projects_collection.get(project_id);
            this.task_m2o.model = project_model;
        },
        on_timer: function(e) {
            var self = this;
            if ($(e.target).hasClass("pt_timer_start")) {
                var current_date = this.get_current_UTCDate();
                this.project_timesheet_db.set_current_timer_activity({date: current_date});
                this.start_interval();
                this.initialize_timer();
                this.$el.find(".pt_timer_start,.pt_timer_stop").toggleClass("o_hidden");
            } else {
                if (!this.is_valid_data()) {
                    alert("Please fill up the required fields ");
                    return;
                }
                if (this.intervalTimer) { clearInterval(this.intervalTimer);}
                var activity = this.project_timesheet_db.load("timer_activity");
                //activity['id'] = _.uniqueId(this.project_timesheet_db.virtual_id_prefix);
                activity['id'] = this.project_timesheet_db.get_unique_id();
                var hours = this.get_date_diff(this.get_current_UTCDate(), activity.date) || 0.01;
                activity['unit_amount'] = hours;
                activity['command'] = 0; //By default command = 0, activity which is to_create
                this.project_timesheet_model.add_activity(activity);
                this.project_timesheet_model.add_project(activity);
                this.$el.find(".pt_timer_start,.pt_timer_stop").toggleClass("o_hidden");
                this.reset_timer();
                this.reload_activity_list();
            }
        },
        start_interval: function() {
            var timer_activity = this.project_timesheet_db.get_current_timer_activity();
            var self = this;
            this.intervalTimer = setInterval(function(){
                self.$el.find(".pt_duration").each(function() {
                    var el_hour = $(this).find("span.hours");
                    var el_minute = $(this).find("span.minutes");
                    if(el_hour == 0 && el_minute == 0)
                        self.$el.find(".pt_duration").css("color","#939392");
                    else
                        self.$el.find(".pt_duration").css("color","#A24689");
                    var minute = parseInt(el_minute.text());
                    if(minute >= 60) {
                        el_hour.text(_.str.sprintf("%02d", parseInt(el_hour.text()) + 1));
                        minute = 0;
                    }
                    el_minute.text(_.str.sprintf("%02d", minute));
                    var el_second = $(this).find("span.seconds");
                    var seconds = parseInt(el_second.text()) + 1;
                    if(seconds >= 60) {
                        el_minute.text(_.str.sprintf("%02d", parseInt(el_minute.text()) + 1));
                        seconds = 0;
                    }
                    el_second.text(_.str.sprintf("%02d", seconds));
                });
            }, 1000);
        },
        is_valid_data: function() {
            if (!this.project_m2o.get('value')) {
                return false;
            }
            return true;
        },
        reset_timer: function() {
            this.$el.find(".pt_duration .hours,.pt_duration .minutes,.pt_duration .seconds").text("00");
            this.project_m2o.destroy();
            this.task_m2o.destroy();
            this.project_timesheet_db.save('timer_activity', {});
        },
        reload_activity_list: function() {
            if (this.activity_list) {this.activity_list.destroy();}
            this.project_timesheet_widget.screen_selector.set_current_screen("activity", {}, {}, true, true);
        },
    });

    project_timesheet.AddActivityScreen = project_timesheet.ScreenWidget.extend({
        template: "AddActivityScreen",
        init: function(project_timesheet_widget, options) {
            this._super.apply(this, arguments);
            this.mode = options.mode || 'create';
            this.current_id = null;
            this.project_timesheet_widget = project_timesheet_widget;
            this._drop_shown = false;
        },
        start: function() {
            var self = this;
            this._super.apply(this, arguments);
            this.$el.find(".pt_btn_add_activity").on("click", this.on_activity_add);
            this.$el.find(".pt_btn_edit_activity").on("click", this.on_activity_edit);
            this.$el.find(".pt_btn_remove_activity").on("click", this.on_activity_remove);
            $(".pt_btn_cancel").on("click", function() {
                self.project_timesheet_widget.screen_selector.set_current_screen("activity");
            });
            
        },
        get_form_data: function() {
            var self = this;
            var project_activity_data = {};
            //$form_data = this.$el.find("input,textarea").filter(function() {return $(this).val() != "";});
            project_activity_data['unit_amount'] = (parseInt(this.$("#hours").val()) + ((((parseInt(this.$("#minutes").val()) * 100) / 60))/100));
            project_activity_data['project_id'] = [self.project_m2o.get("value"), self.project_m2o.get("display_string")];
            project_activity_data['task_id'] = [self.task_m2o.get("value"), self.task_m2o.get("display_string")];
            project_activity_data['name'] = this.$("#name").val();
            return project_activity_data;
        },
        on_activity_add: function() {
            if (!this.is_valid_data()) {
                return;
            }
            var project_activity_data = this.get_form_data();
            var momObj = new moment();
            var date = project_timesheet.datetime_to_str(momObj._d);
            project_activity_data['date'] = date; //Current date in accepted format
            //project_activity_data['id'] = _.uniqueId(this.project_timesheet_db.virtual_id_prefix); //Activity New ID
            project_activity_data['id'] = this.project_timesheet_db.get_unique_id();
            project_activity_data['command'] = 0; //By default command = 0, activity which is to_create
            this.project_timesheet_model.add_activity(project_activity_data);
            this.project_timesheet_model.add_project(project_activity_data);
            this.project_timesheet_widget.screen_selector.set_current_screen("activity", {}, {}, false, true);
        },
        on_activity_edit: function() {
            if (!this.is_valid_data()) {
                return;
            }
            var project_activity_data = this.get_form_data();
            console.log("project_activity_data is inside edit ::: ", project_activity_data);
            project_activity_data['id'] = this.current_id; //Activity Existing ID
            project_activity_data['command'] = 1;
            this.project_timesheet_model.add_activity(project_activity_data);
            this.project_timesheet_model.add_project(project_activity_data);
            this.project_timesheet_widget.screen_selector.set_current_screen("activity", {}, {}, false, true);
        },
        on_activity_remove: function() {
            //This method will set activity command to 2, so while synchronize we will set that activty as a to_delete
            var project_activity_data = this.get_form_data();
            project_activity_data['id'] = this.current_id; //Activity Existing ID
            var activities_collection = this.project_timesheet_model.get("activities");
            if(activities_collection.get(project_activity_data.id)) {
                var activity_model = activities_collection.get(project_activity_data.id);
                if (this.current_id.toString().match(this.project_timesheet_db.virtual_id_regex)) {
                    activities_collection.remove(activity_model);
                    this.project_timesheet_db.remove_activity(project_activity_data);
                } else {
                    activity_model.command = 2;
                    project_activity_data.command = 2;
                    this.project_timesheet_db.add_activity(project_activity_data);
                }
            }
            this.project_timesheet_widget.screen_selector.set_current_screen("activity", {}, {}, false, true);
        },
        show: function() {
            var self = this;
            $form_data = this.$el.find("input,textarea").filter(function() {return $(this).val() != "";});
            $form_data.val('');
            this.$el.find(".pt_activity_body h4,.pt_btn_add_activity").removeClass("o_hidden");
            self.$el.find(".pt_btn_remove_activity").addClass("o_hidden");
            if(!this.$el.find(".pt_btn_edit_activity").hasClass("o_hidden")) {
                this.$el.find(".pt_btn_edit_activity").addClass("o_hidden");
            }
            $form_data.removeData();
            this.activity_list = new project_timesheet.ActivityListView();
            this.activity_list.appendTo(this.$el.find(".pt_activity_body"));
            this.activity_list.$el.find(".activity_row").on('click', this.on_click_row);
            this._super();
            //Need to create instance of many2one in show method, because when autocomplete input is hidden, and show again it throws event binding error, we need to develop destroy_content in many2one widget and need to call when screen is hidden, need to bind events of many2one in show screen
            this.project_m2o = new project_timesheet.FieldMany2One(this, {model: this.project_timesheet_model , classname: "pt_input_project pt_required", label: "Project", id_for_input: "project_id"});
            this.project_m2o.$el.find("textarea").on("change", this, function() {
                this.task_m2o.set({display_string: false, value: false});
                this.task_m2o.display_string(false);
                this.set_project_model();
            });
            this.project_m2o.appendTo(this.$el.find(".project_m2o"));
            this.task_m2o = new project_timesheet.FieldMany2One(this, {model: false, search_model: 'task', classname: "pt_input_task", label: "Task", id_for_input: "task_id"});
            this.task_m2o.appendTo(this.$el.find(".task_m2o"));
        },
        hide: function() {
            if(this.activity_list) {
                this.activity_list.destroy();
            }
            if(this.project_m2o) {
                this.project_m2o.destroy();
            }
            if(this.task_m2o) {
                this.task_m2o.destroy();
            }
            this._super();
        },
        on_click_row: function(event) {
            var activity_id = $(event.currentTarget).data("activity_id");
            var activity = this.project_timesheet_db.get_activity_by_id(activity_id);
            var activity_clone = _.clone(activity);
            //activity_clone.id = _.uniqueId(this.project_timesheet_db.virtual_id_prefix); //Activity New ID
            activity_clone.id = this.project_timesheet_db.get_unique_id();
            this.project_timesheet_model.add_project(activity_clone);
            this.project_timesheet_model.add_activity(activity_clone);
            this.project_timesheet_widget.screen_selector.set_current_screen("activity", {}, {}, false, true);

        },
        is_valid_data: function() {
            var validity = true;
            var $required_inputs = this.$el.find("input.pt_required,textarea.pt_required").filter(function() {return $(this).val() == "";});
            _.each($required_inputs, function(input) {
                $(input).addClass("pt_invalid");
                validity = false;
            });
            var $duration_field = this.$el.find(".pt_duration input");
            _.each($duration_field, function(input) {
                if(!$(input).val() || (typeof parseInt($(input).val()) !== 'number' || isNaN(parseInt($(input).val())))) {
                    $(input).addClass("pt_invalid");
                    validity = false;
                }
            });
            return validity;
        },
        set_project_model: function() {
            var project_id = this.project_m2o.get('value');
            var projects_collection = this.project_timesheet_model.get('projects');
            var project_model = projects_collection.get(project_id);
            this.task_m2o.model = project_model;
        },
        format_duration: function(field_val) {
            var data = field_val.toString().split(".");
            if (data[1]) {
                data[1] = Math.round((field_val%1)*60);
                if (data[1] == 60) {
                    data[1] = 0;
                    data[0] = parseInt(data[0]) + 1;
                }
            }
            return data;
        },
        set_screen_values: function(screen_data) {
            //This method is called when its edit mode(i.e. when row is clicked from Activity Listview)
            var self = this;
            this.mode = "edit";
            this.current_id = screen_data['id'];
            this.$el.find(".pt_activity_body table").remove();
            this.$el.find(".pt_activity_body h4").addClass("o_hidden");
            self.$el.find(".pt_btn_remove_activity").removeClass("o_hidden");
            self.$el.find(".pt_btn_edit_activity,.pt_btn_add_activity").toggleClass("o_hidden");
            this.task_m2o.set({"effective_readonly": true});
            this.project_m2o.set({"effective_readonly": true});
            _.each(screen_data, function(field_val, field_key) {
                switch(field_key) {
                    case "project_id":
                        self.project_m2o.set({display_string: field_val[1], value: field_val[0]});
                        self.project_m2o.display_string(field_val);
                        break;
                    case "task_id":
                        self.task_m2o.set({display_string: field_val[1], value: field_val[0]});
                        self.task_m2o.display_string(field_val);
                        break;
                    case "unit_amount":
                        var formatted = self.format_duration(field_val);
                        self.$el.find("#hours").val(formatted[0]);
                        self.$el.find("#minutes").val(formatted[1]);
                        break;
                    case "name":
                        self.$el.find("#"+field_key).val(field_val);
                        break;
                }
            });
        },
    });

    //TODO: We can override show method, when user document's cookie is already set with session_id then do not ask for server name, db, username, and password, directy give Synchronize button
    //When Sync screen is displayed check session first whether session_id exist then call reload session and do not display db, username, password elements
    //May be give message in template that you are already logged in, login with other user ?
    project_timesheet.SyncScreen = project_timesheet.ScreenWidget.extend({
        template: "SyncScreen",
        init: function(project_timesheet_widget, options) {
            this._super.apply(this, arguments);
            this.project_timesheet_widget = project_timesheet_widget;
        },
        start: function() {
            var self = this;
            this._super.apply(this, arguments);
            this.$el.find(".pt_select_protocol").on("click", function() {
                self.$el.find(".pt_button_protocol span:first").text($(this).text());
            });
            this.$el.find("#pt_new_user,#pt_existing_user").on("click", function() {
                self.$el.find(".o_new_account").toggleClass("o_active");
                self.$el.find(".o_existing_account").toggleClass("o_active");
            });
            this.$el.find(".pt_btn_synchronize_existing_account").on("click", this.on_sync);
            this.$el.find(".pt_btn_synchronize").on("click", this.on_authenticate_and_sync);
            $(".pt_btn_cancel").on("click", function() {
                self.project_timesheet_widget.screen_selector.set_current_screen("activity");
            });
        },
        renderElement: function() {
            this.replaceElement(QWeb.render(this.template, {widget: this, project_timesheet: project_timesheet}));
        },
        on_authenticate_and_sync: function() {
            var self = this;
            var def = $.Deferred();
            var protocol = self.$el.find(".pt_button_protocol span:first").text();
            var origin = protocol + this.$el.find(".pt_input_server_address").val(); //May be store origin in localstorage to keep session persistent for that origin
            var db = this.$el.find(".pt_input_db").val();
            var username = this.$el.find(".pt_input_username").val();
            var password = this.$el.find(".pt_input_password").val();
            if(!_.all([origin, db, username, password])) {
                this.set_required();
                return;
            }
            //TODO: Check whether we already having session, if yes then use it by just reloading session
            var session = new openerp.Session(undefined, origin);
            project_timesheet.session = session;
            //if (!openerp.get_cookie("session_id")) { //use check_session_id
                def = session.session_authenticate(db, username, password).done(function() {
                    //TODO: Create generic method set_cookie
                    document.cookie = ["session_id="+session.session_id,'path='+origin,
                        'max-age=' + (24*60*60*365),
                        'expires=' + new Date(new Date().getTime() + 300*1000).toGMTString()].join(';');

                        //Store session object in local storage, we need it, so that user don't have to enter login detail each time while sync
                        //Note that, session_id is created new each time for cross domain policy
                        self.project_timesheet_db.save("session", session);
                }).fail(function(error, event) {
                    if (error) {
                        self.rpc_error(error);
                    } else {
                        alert("Something went wrong, please check your username or password");
                    }
                });
            //} else {
            //    def.resolve();
            //}
            $.when(def).done(function() {
                console.log("You can go ahead to sync data and retrieve data");
                //Get Model data and sync with Server and then Retrieve data and store in localstorage
                self.on_sync();
            });
        },
        on_sync: function() {
            var self = this;
            this.project_timesheet_model.save_to_server().then(function() { //May be user always
                console.log("Inside save to server completed ::: ");
                //TODO: Show dialog sync related detail
                self.project_timesheet_widget.screen_selector.set_current_screen("activity", {}, {}, false, true);
            });
        },
        set_required: function() {
            var origin = this.$el.find(".pt_input_server_address"); //May be store origin in localstorage to keep session persistent for that origin
            var db = this.$el.find(".pt_input_db");
            var username = this.$el.find(".pt_input_username");
            var password = this.$el.find(".pt_input_password");
            var first_elem = _.find([origin, db, username, password], function(ele) {return !ele.val();});
            first_elem.focus();
            _([origin, db, username, password]).each(function($element) {
                $element.removeClass('oe_form_required');
                if (!$element.val()) {
                    $element.addClass('pt_invalid');
                }
            });
            
        },
    });

    project_timesheet.StatisticScreen = project_timesheet.ScreenWidget.extend({
        template: "StatisticScreen",
        events: {
            "click .pt_prev_week,.pt_next_week": "on_navigation",
        },
        init: function(project_timesheet_widget, options) {
            this._super.apply(this, arguments);
            this.project_timesheet_widget = project_timesheet_widget;
            this.week_index = 0;
        },
        start: function() {
            var self = this;
            this._super.apply(this, arguments);
        },
        show: function() {
            var self = this;
            this._super();
            this.$el.find(".pt_back").on("click", function() {
                console.log("Insife backkkk ");
                self.project_timesheet_widget.screen_selector.set_current_screen("activity", {}, {}, false, true);
            });
            this.$el.find(".pt_sync").on("click", function() {
                self.project_timesheet_widget.screen_selector.set_current_screen("sync");
            });
            this.bar_chart = this.prepare_graph();
            this.graph_data = this.prepare_data();
            console.log("graph_data is ::: ", this.graph_data);
            if (this.graph_data.length && this.graph_data[this.week_index].length) {
                this.draw_chart(this.bar_chart, this.graph_data[this.week_index]);
            }
        },
        hide: function() {
            this._super();
            console.log("this.bar_chart is :: ", this.bar_chart);
            if (this.bar_chart) {
                this.bar_chart.clearAll();
                this.bar_chart.clearCanvas();
                this.bar_chart = {};
                this.$(".dhx_chart_legend").remove(); //Hack: forcefully remove legend also when graph is navigate is we are going to redraw whole graph again
                console.log("Inside iffff ", this.bar_chart);
            }
        },
        prepare_graph: function() {
            var self = this;
            var bar_chart =  new dhtmlXChart({
                view: "stackedBar",
                container: "pt_chart",
                value: "#unit_amount#",
                label: "#unit_amount#"+"h",
                color: "#a24689",
                width: 25,
                //gradient:"falling",
                tooltip: {
                    template:"#unit_amount#"+"h", 
                },
                xAxis: {
                    title: "Days",
                    template: "#day#",
                    lines: false
                },
                yAxis: {
                    title: "Hours",
                    start: 0,
                    // step:5,
                    // end:24
                },
                legend: {
                    values: [{text:"Compeleted Activities",color:"#a24689"},{text:"Undefined activities",color:"#ffcc00"}],
                    valign: "top",
                    align: "center",
                    width: 110,
                    layout: "x",
                    marker: {
                        type: "round",
                        width: 15,
                        height: 15
                    }
                },
                border: 0,
            });

            bar_chart.addSeries({
                value:"#unallocated#",
                color:"#ffcc00",
                label:"#unallocated#",
                tooltip:{
                    template:"#unallocated#"
                }
            });
            return bar_chart;
        },
        prepare_data: function() {
            var date_groups;
            var activities = _.clone(this.project_timesheet_db.load("activities"));
            var date_activities = {};
            _.map(activities, function(activity) {
                delete activity.id;
                delete activity.name;
            });
            date_groups = _.groupBy(activities, function(activity) {
                return moment(activity.date).format("YYYY-MM-DD");
            });
            _.map(date_groups, function(groups, key) {
                _.each(groups, function(group) {
                    if (date_activities[key]) {
                        if (date_activities[key]['task_id']) {
                            date_activities[key]['unit_amount'] += parseFloat((group.unit_amount).toFixed(2));
                        } else {
                            date_activities[key]['unallocated'] += parseFloat((group.unit_amount).toFixed(2));
                        }
                    } else {
                        group['unallocated'] = 0;
                        group['unit_amount'] = parseFloat((group.unit_amount).toFixed(2));
                        group['day'] = moment(group.date).format("ddd MM");
                        date_activities[key] = group;
                    }
                });
            });
            var week_groups = _.groupBy(_.toArray(date_activities), function(activity) {
                return moment(activity.date).week();
            });
            var week_wise_activities = _.map(week_groups, function(group, key) {
                return group;
            });
            return week_wise_activities;
        },
        draw_chart: function(chart, graph_data) {
            console.log("Inside draw_chart ::: ");
            var week_total = 0;
            var table_data = {};
            _.each(graph_data, function(record) {week_total += record.unit_amount;});
            formatted_value = this.format_duration(week_total);
            this.$el.find(".pt_stat_week_title").text(_.str.sprintf("%sh %smin this week", formatted_value[0], (formatted_value[1] || 0)));
            var project_groups = _.groupBy(graph_data, function(record) {
                return record.project_id[0];
            });
            _.each(project_groups, function(groups, key) {
                _.each(groups, function(group) {
                    if (table_data[key]) {
                        table_data[key]['unit_amount'] += group.unit_amount;
                    } else {
                        table_data[key] = {
                            project_name: group.project_id[1],
                            unit_amount: group.unit_amount
                        };
                    }
                });
            });
            this.$el.find(".pt_stat_table").html(QWeb.render('StatisticTable', {widget: this, projects: _.toArray(table_data)}));
            chart.parse(graph_data,"json");
        },
        format_duration: function(duration) {
            var add_activity_screen = this.project_timesheet_widget.add_activity_screen;
            return add_activity_screen.format_duration(duration);
        },
        on_navigation: function(e) {
            this.bar_chart.clearAll();
            this.bar_chart.clearCanvas();
            this.$(".dhx_chart_legend").remove(); //Hack: forcefully remove legend also when graph is navigate is we are going to redraw whole graph again
            if ($(e.target).data("direction") == "next") {
                this.week_index += 1;
                if (this.week_index > this.graph_data.length-1) {
                    this.week_index = 0;
                }
            } else {
                this.week_index -= 1;
                if (this.week_index < 0) {
                    this.week_index = this.graph_data.length-1;
                }
            }
            this.draw_chart(this.bar_chart, this.graph_data[this.week_index]);
        },
        get_pending_lines: function() {
            return this.project_timesheet_model.get_pending_records();
        }
    });
}