function odoo_project_timesheet_widgets(project_timesheet) {
    //var QWeb = openerp.qweb,
    var QWeb = project_timesheet.qweb,
    _t = openerp._t;

    project_timesheet.project_timesheet_widget = openerp.Widget.extend({
        template: "ProjectTimesheet",
        init: function() {
            this._super.apply(this, arguments);
            /** Setup default session */
            //openerp.session = new instance.web.Session(); //May be store in this object, no need to store in openerp global
            //project_timesheet.project_timesheet_model = new project_timesheet.project_timesheet_model(openerp.session, {project_timesheet_widget: this}); //May be store in this
            project_timesheet.project_timesheet_model = new project_timesheet.project_timesheet_model({project_timesheet_widget: this}); //May be store in this, we'll not have session initially, need to discuss how to manage session
        },
        start: function() {
            this._super.apply(this, arguments);
            //Add the concept of screen, screen will decide which widgets to render at which position
            //var pt_activity = new project_timesheet.ActivityScreen(this, {});
            //pt_activity.replace(this.$el.find(".content_area"));
            //var pt_footer = new project_timesheet.FooterWidget(this, {});
            //pt_footer.replace(this.$el.find(".pt_footer"));
            this.build_widgets();
            this.screen_selector.set_default_screen();
        },
        build_widgets: function() {
            //Creates all widgets instances and add into this object
            /*----------------Screen------------------*/
            this.activity_screen = new project_timesheet.ActivityScreen(this, {project_timesheet_model: project_timesheet.project_timesheet_model});
            //Append all screen widget in screen element of this.$el, by default all will be hidden and then current screen will be visible
            this.activity_screen.appendTo(this.$('.screens'));

            this.add_activity_screen = new project_timesheet.AddActivityScreen(this, {project_timesheet_model: project_timesheet.project_timesheet_model});
            this.add_activity_screen.appendTo(this.$('.screens'));

            this.modify_activity_screen = new project_timesheet.ModifyActivityScreen(this, {project_timesheet_model: project_timesheet.project_timesheet_model});
            this.modify_activity_screen.appendTo(this.$('.screens'));

            this.sync_screen = new project_timesheet.SyncScreen(this, {project_timesheet_model: project_timesheet.project_timesheet_model});
            this.sync_screen.appendTo(this.$('.screens'));

            this.stat_screen = new project_timesheet.StatisticScreen(this, {project_timesheet_model: project_timesheet.project_timesheet_model});
            this.stat_screen.appendTo(this.$('.screens'));

            /*----------------Screen Selector------------------*/
            this.screen_selector = new project_timesheet.ScreenSelector({
                project_timesheet_model: project_timesheet.project_timesheet_model,
                screen_set:{
                    'activity': this.activity_screen,
                    'sync' : this.sync_screen,
                    'add_activity': this.add_activity_screen,
                    'modify_screen':    this.modify_activity_screen,
                    'stat' : this.stat_screen,
                },
                default_screen: 'activity',
            });
        },
    });

    //TO REMOVE
    project_timesheet.FooterWidget = openerp.Widget.extend({
        template: "Footer",
        init: function() {
            this._super.apply(this, arguments);
        },
        start: function() {
            this._super.apply(this, arguments);
        }
    });
}