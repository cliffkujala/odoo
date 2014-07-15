(function() {
    "use strict";
    var instance = openerp;
    var QWeb = instance.web.qweb;
    instance.planner = {};


    instance.web.WebClient.include({
        start: function() {
            this.planner_manager =  new instance.planner.PlannerManager();
            return this._super.apply(this, arguments);
        },
        show_application: function() {
            var self = this;
            this._super.apply(this, arguments);
            self.menu.on("on_top_menu_click", self.planner_manager, self.planner_manager.on_menu_clicked);
        }
    });

    instance.web.Menu.include({
        on_top_menu_click: function(ev) {
            this._super.apply(this, arguments);
            this.trigger('on_top_menu_click', $(ev.currentTarget).data('menu'));
            this.reflow(); //to handle progressbar display in case of menu overflowing
        }
    });

    instance.planner.PlannerManager = instance.web.Widget.extend({
        init: function() {
            this._super();
            var self = this;
            self.fetch_application_planner().done(function(apps) {
                self.planner_apps = apps;
            });
        },
        on_menu_clicked: function(menu_id) {
            var self = this;
            self.planner_launcher && self.planner_launcher.destroy();
            if (_.contains(_.keys(self.planner_apps), ''+menu_id)) {
                self.planner_launcher = new instance.planner.PlannerLauncher(self, self.planner_apps[menu_id]);
                self.planner_launcher.prependTo(window.$('.oe_systray'));
            }
        },
        fetch_application_planner: function() {
            var self = this;
            var def = $.Deferred();
            if (this.planner_bymenu) {
                def.resolve(self.planner_bymenu);
            } else {
                self.planner_bymenu = {};
                (new instance.web.Model('planner.planner')).query().all().then(function(res) {
                    _(res).each(function(planner) {
                        self.planner_bymenu[planner.menu_id[0]] = planner;
                    });
                    def.resolve(self.planner_bymenu);
                }).fail(function() {def.reject();});
            }
            return def;
        }

    });

    /**
        this widget handles the show/hide of progress bar base on menu clicked by the users,
        fetch applications planner data from database, and instantiate the PlannerDialog.
    */
    instance.planner.PlannerLauncher = instance.web.Widget.extend({
        template: "PlannerLauncher",
        events: {
            'click .oe_planner_progress': 'toggle_dialog'
        },

        init: function(parent, data) {
            this._super(parent);
            this.planner_data = data;
            this.dialog = new instance.planner.PlannerDialog(this);
        },
        start: function() {
            this.$(".oe_planner_progress").tooltip({html: true, title: this.planner_data.tooltip_planner, placement: 'bottom', delay: {'show': 500}});
            this.update_progress_value(this.planner_data.progress);
            this.dialog.appendTo(document.body);
            return this._super.apply(this, arguments);
        },
        update_progress_value: function(progress_value) {
            this.$(".progress-bar").css('width', progress_value+"%");
        },
        toggle_dialog: function() {
            this.dialog.$('#PlannerModal').modal('toggle');
        }
    });


    /**
        this widget handles the display of planner dialog and all the pages of planner,
        and also handles some operations like go to next page, mark step as done,
        store user's filled values into database etc...
    */
    instance.planner.PlannerDialog = instance.web.Widget.extend({
        template: "PlannerDialog",
        events: {
            'show.bs.modal': 'show',
            'hide.bs.modal': 'hide',
            'click .oe_planner div[id^="planner_page"] a[href^="#planner_page"]': 'next_page',
            'click .oe_planner li a[href^="#planner_page"]': 'onclick_menu',
            'click .oe_planner div[id^="planner_page"] button[data-progress^="planner_page"]': 'mark_as_done'
        },

        init: function(parent) {
            this._super(parent);
            this.planner_launcher = parent;
            this.planner_data = this.planner_launcher.planner_data;
            this.values = {}; // to store values and id of all input elements
            this.set('progress', 0);
        },
        start: function() {
            this.load_page();
            this.on('change:progress', this, this.update_ui_progress_bar);
            return this._super.apply(this, arguments);
        },
        onclick_menu: function(ev) {
            ev.stopPropagation();
            var page_id = $(ev.currentTarget).attr('href').replace('#', '');
            this._switch_page(page_id);
        },
        next_page: function(ev) {
            ev.stopPropagation();
            var next_page_id = $(ev.currentTarget).attr('href').replace('#', '');
            this._switch_page(next_page_id);
        },
        _switch_page: function(planner_page_id) {
            this.$(".oe_planner li a[href^='#planner_page']").parent().removeClass('active');
            this.$(".oe_planner li a[href=#"+planner_page_id+"]").parent().addClass('active');
            this.$(".oe_planner div[id^='planner_page']").removeClass('in');
            this.$(".oe_planner div[id="+planner_page_id+"]").addClass('in');
            this.values['last_open_page'] = planner_page_id;
        },
        mark_as_done: function(ev) {
            var self = this;
            var btn = $(ev.currentTarget);
            var active_menu = self.$(".oe_planner li a[href=#"+btn.attr('data-progress')+"] span");
            var active_page = self.$(".oe_planner div[id^='planner_page'].panel-collapse.collapse.in");

            //find all inputs elements of current page
            var input_element = self.$(".oe_planner div[id="+btn.attr('data-progress')+"] textarea[id^='input_element'], .oe_planner div[id="+btn.attr('data-progress')+"] input[id^='input_element'], select[id^='input_element']");
            var next_button = self.$(".oe_planner a[data-parent="+btn.attr('data-progress')+"]");
            if (!btn.hasClass('fa-check-square-o')) {
                //find menu element and marked as check
                active_menu.addClass('fa-check');
                //mark checked on button
                btn.addClass('fa-check-square-o btn-default').removeClass('fa-square-o btn-primary');
                next_button.addClass('btn-primary').removeClass('btn-default');
                self.update_input_value(input_element, true);
                self.values[btn.attr('id')] = 'checked';
                self.set('progress', self.get('progress') + 1);
                active_page.addClass('marked');
                setTimeout(function() { active_page.removeClass('marked'); }, 1000);

            } else {
                btn.removeClass('fa-check-square-o btn-default').addClass('fa fa-square-o btn-primary');
                next_button.addClass('btn-default').removeClass('btn-primary');
                active_menu.removeClass('fa-check');
                self.values[btn.attr('id')] = '';
                self.update_input_value(input_element, false);
                self.set('progress', self.get('progress') - 1);
            }

            self.planner_data['progress'] = parseInt((self.get('progress') / self.btn_mark_as_done.length) * 100, 10);
            self.planner_data['data'] = JSON.stringify(self.values);
            self.planner_launcher.update_progress_value(self.planner_data['progress']);
            //call save_planner_data to store JSON data into database
            self.save_planner_data();
        },

        /**
            @param {boolean} save If set to true, store values of all input elements of current page
            else clear the values of input elements.
        */
        update_input_value: function(input_element, save) {
            var self = this;
            _.each(input_element, function(element) {
                var $el = $(element);
                if ($el.attr('type') == 'checkbox' || $el.attr('type') == 'radio') {
                    if ($el.is(':checked') && save) {
                        self.values[$el.attr("id")] = 'checked';
                        $el.attr('checked', 'checked');
                    } else {
                        self.values[$el.attr("id")] = "";
                    }
                } else { 
                    if (save) {
                        self.values[$el.attr("id")] = $el.val();
                        //set value to input element, to get those value when printing report
                        $el.attr('value', $el.val());
                    } else {
                        self.values[$el.attr("id")] = "";
                    }
                }
            });
        },
        save_planner_data: function() {
            return (new instance.web.DataSet(this, 'planner.planner'))
                .call('write', [this.planner_data.id, {'data': this.planner_data.data, 'progress': this.planner_data['progress']}]);
        },
        add_footer: function() {
            var self = this;
            //find all the pages and append footer to each pages
            _.each(self.$('.oe_planner div[id^="planner_page"]'), function(element) {
                var $el = $(element);
                var next_page_name = self.$(".oe_planner .side li a[href='#"+$el.next().attr('id')+"']").text() || ' Finished!';
                var footer_template = QWeb.render("PlannerFooter", {
                    'next_page_name': next_page_name,
                    'next_page_id': $el.next().attr('id'),
                    'current_page_id': $el.attr('id'),
                    'start': $el.prev().length ? false: true,
                    'end': $el.next().length ? false: true
                });
                $el.append(footer_template);
            });
        },
        set_all_input_id: function() {
            var self = this;
            self.values['last_open_page'] = '';
            _.each(self.input_elements, function(element) {
                var $el = $(element);
                if ($el.attr('type') == 'checkbox' || $el.attr('type') == 'radio') {
                    self.values[$el.attr("id")] = '';
                } else {
                    self.values[$el.attr("id")] = $el.val();
                }
            });
            _.each(self.btn_mark_as_done, function(element) {
                var $el = $(element);
                self.values[$el.attr("id")] = '';
            });
        },

        /**
            this method fill the values of each input element from JSON data
            @param {object} JSON data
        */
        fill_input_data: function(input_data) {
            var self = this;
            if (!_.size(input_data)) {
                //when planner is launch for the first time, we need to store the id of each elements into database.
                self.set_all_input_id();
            } else {
                self.values = _.clone(input_data);
            }
            _.each(input_data, function(val, id){
                if ($('#'+id).prop("tagName") == 'BUTTON') {
                    if (val == 'checked') {
                        self.set('progress', self.get('progress') + 1);
                        //find those menu which are all ready marked as done and checked them
                        self.$("li a[href=#"+$('#'+id).attr('data-progress')+"] > span").addClass('fa-check');
                        var page_id = self.$('#'+id).addClass('fa-check-square-o btn-default').removeClass('fa-square-o btn-primary').attr('data-progress');
                        self.$(".oe_planner .planner_footer a[data-parent="+page_id+"]").addClass('btn-primary').removeClass('btn-default');
                    }
                } else if ($('#'+id).prop("tagName") == 'INPUT' && ($('#'+id).attr('type') == 'checkbox' || $('#'+id).attr('type') == 'radio')) {
                    if (val == 'checked') {
                        self.$('#'+id).attr('checked', 'checked');
                    }
                } else {
                    //Set value using attr, to get those value while printing report
                    self.$('#'+id).attr('value', val);
                }
            });
        },
        load_page: function() {
            var self = this;
            (new instance.web.DataSet(this, 'planner.planner')).call('render', [self.planner_data.view_id[0], self.planner_data.planner_application]).then(function(res) {
                self.$('.content_page').html(res);
                self.planner_data.data = jQuery.parseJSON(self.planner_data.data) || {};
                //add footer to each page
                self.add_footer();
                //find all input elements having id start with 'input_element'
                self.input_elements = self.$(".oe_planner textarea[id^='input_element'], .oe_planner input[id^='input_element'], select[id^='input_element']");
                //find 'mark as done' button to calculate the progress bar.
                self.btn_mark_as_done = self.$(".oe_planner button[id^='input_element'][data-progress^='planner_page']");
                self.fill_input_data(self.planner_data.data);
                //show last opened page
                var last_open_page = self.planner_data.data && self.planner_data.data['last_open_page'];
                if (last_open_page) {
                    $(".oe_planner li a[href='#"+last_open_page+"']").trigger('click');
                }

                /*==== Stefano ====  Call resize function at the beginning*/
                self.winDim();

                $(document).on('keyup load change', "textarea", function() {
                    if (this.scrollHeight != this.clientHeight) {
                        this.style.height = this.scrollHeight + "px";
                    }
                });
            });
        },
        // ==== Stefano ==== Resize function for dinamically fix columns height
        winDim: function() {
            var winH  = $(window).height();
            var $modal = this.$('.planner-dialog');
            $modal.height(winH/1.1);
            this.$('.pages').height($modal.height() - 60);
            this.$('.side').height($modal.height() - 75);
        },
        show: function() {
            var self = this;
            $(window).on('resize', function() {
                self.winDim();
            });
        },
        hide: function() {
            //store updated input values when modal is close.
            this.planner_data['data'] = JSON.stringify(this.values);
            this.save_planner_data();
        },
        update_ui_progress_bar: function() {
            var progress_bar_val = parseInt((this.get('progress')/this.btn_mark_as_done.length)*100, 10);
            this.$(".progress-bar").css('width', progress_bar_val+"%");
            this.$(".progress_col").find('span.counter').text(progress_bar_val+"%");
        }

    });

})();
