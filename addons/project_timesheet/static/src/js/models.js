function odoo_project_timesheet_models(project_timesheet) {

    project_timesheet.task_activity_model = Backbone.Model.extend({
        initialize: function(attributes, options) {
            Backbone.Model.prototype.initialize.call(this, attributes);
            this.id = options.id || null;
            this.date = options.date || null;
            this.task_id = options.task_id || null;
            this.project_id = options.project_id || null;
            this.name = options.name || null; //Actually description field
            this.unit_amount = options.unit_amount || null;
            this.reference_id = options.reference_id || null;
            this.command = options.command;
            this.__last_update = options.__last_update || false;
        },
        export_as_JSON: function() {
            return {
                id: this.id,
                date: this.date || project_timesheet.datetime_to_str(new moment()._d),
                name: this.name || '/',
                unit_amount: this.unit_amount,
                command: this.command,
                task_id: this.task_id,
                project_id: this.project_id,
                reference_id: this.reference_id,
                user_id: project_timesheet.session.uid,
                __last_update: this.__last_update,
                
            };
        },
    });

    project_timesheet.TaskActivityCollection = Backbone.Collection.extend({
        model: project_timesheet.task_activity_model,
    });


    //Note: Regarding project already connected or not ? state: "connecting", //There will be two state, connecting and connected, if record is modified then again state will be changed and localstorage will be updated
    project_timesheet.task_model = Backbone.Model.extend({
        initialize: function(attributes, options) {
            Backbone.Model.prototype.initialize.call(this, attributes);
            this.project_timesheet_widget = attributes.project_timesheet_widget;
            this.project_timesheet_db = attributes.project_timesheet_db;
            this.id = options.id || null;
            this.name = options.name || null;
            this.project_id = options.project_id || null;
            this.priority = options.priority || 0;
        },
    });

    project_timesheet.TaskCollection = Backbone.Collection.extend({
        model: project_timesheet.task_model,
    });

    project_timesheet.project_model = Backbone.Model.extend({
        initialize: function(attributes, options) {
            Backbone.Model.prototype.initialize.call(this, attributes);
            this.project_timesheet_model = attributes.project_timesheet_model;
            this.project_timesheet_db = attributes.project_timesheet_db;
            this.id = options.id || null; //If no real id, we will have virtual id, at sync time virtual id will be skipped while sending data to server
            this.name = options.name || null;
            this.set({
                tasks: new project_timesheet.TaskCollection(),
            });
        },
        add_task: function(data) {
            tasks_collection = this.get("tasks");
            if (tasks_collection.get(data.task_id[0])) {
                var task_model = tasks_collection.get(data.task_id[0]);
            } else {
                var task = new project_timesheet.task_model({project_timesheet_db: this.project_timesheet_db}, {id: data['task_id'][0], name: data['task_id'][1], project_id: data['project_id'][0], priority: data['priority']});
                this.get('tasks').add(task);
            }
        },
        name_search: function(term) {
            /*
             * This method will search into task collection and will return key, value pairs for tasks
             */
            var tasks = this.get('tasks');
            var search_result = [];
            var task_models = tasks.models;
            for (var i = 0; i < task_models.length; i++) {
                search_result.push([task_models[i].id, task_models[i].name+"\n"+task_models[i].priority]);
            }
            if (term) {
                search_result = _.compact(_(search_result).map(function(x) {if (x[1].toLowerCase().contains(term.toLowerCase())) {return x;}}));
            }
            return search_result;
        }
    });

    project_timesheet.ProjectCollection = Backbone.Collection.extend({
        model: project_timesheet.project_model,
    });

    //Once data has been sync, read project, then task and activities and store it into localstorage also
    //While sync read model, this following model's save_to_server will fetch project, and project will fetch task in format such that its one2many
    //Also add the logic of destroy model

    project_timesheet.project_timesheet_model = Backbone.Model.extend({
        initialize: function(attributes) {
            var self = this;
            var callback_function;
            Backbone.Model.prototype.initialize.call(this, attributes);
            this.project_timesheet_widget = attributes.project_timesheet_widget;
            this.def = $.Deferred();
            this.ready = $.Deferred();
            this.set({
                projects: new project_timesheet.ProjectCollection(),
                activities: new project_timesheet.TaskActivityCollection(),
            });
            this.project_timesheet_db = new project_timesheet.project_timesheet_db();
            this.screen_data = {};  //see ScreenSelector
            //Try to check localstorage having session, we do not reload session like web module(core.js), instead stored in localstorage to keep persistent origin
            console.log("project_timesheet is ::: ", project_timesheet, openerp);
            if(!project_timesheet.session && !_.isEmpty(this.project_timesheet_db.load("session", {}))) {
                var stored_session = this.project_timesheet_db.load("session", {});
                //project_timesheet.session = new openerp.Session(undefined, stored_session['origin'], {session_id: stored_session['session_id']});
                project_timesheet.session = new openerp.Session(undefined, stored_session['origin']);
            }
            //If we have stored session then replace project_timesheet.session with new Session object with stored session origin
            if (!_.isEmpty(project_timesheet.session)) {
                callback_function = function () {
                    //Important Note: check_session_id may replace session_id each time when server_origin is different then origin,
                    //so we will update the localstorage session
                    self.project_timesheet_db.save("session", project_timesheet.session);
                    console.log("Here we go, you can do rpc, we having session ID.");
                };
                //this.def = project_timesheet.session.check_session_id();
                this.def = project_timesheet.session.session_reload();
            } else {
                callback_function = function () {
                    //TODO: To check we should clear activitie here or not ?
                    //Check Scenario: Login with db1, open project timesheet interface, do some entries, logout from that database from backend view and login with other db, still old db localstorage will be there
                    //self.project_timesheet_db.clear('activities');
                    project_timesheet.session = session;
                    self.project_timesheet_db.save("session", project_timesheet.session);
                };
                //If we do not have previous stored session then try to check whether we having session with window origin (say for example session with localhost:9000)
                console.log("Inside elseeee, we do not have old session stored with origin in db");
                var isLocal = location.protocol === "file:";
                if (isLocal) {
                    this.def.reject();
                } else {
                    var window_origin = location.protocol + "//" + location.host;
                    var session = new openerp.Session(undefined, window_origin);
                    this.def = session.session_reload();
                }
            }
            //Always Load locally stored data, whether server is running(or def may fail, because server is not up, still we will load local data)
            this.def.done(function() {
                callback_function();
                self.load_server_data().done(function() {
                    self.load_stored_data();
                    new project_timesheet.Model(project_timesheet.session, "ir.model.data")
                    .call("get_object_reference", ['hr_timesheet', 'menu_hr_timesheet_report_all'])
                    .then(function (result) {
                        if (result) {
                            self.reporting_menu_src = project_timesheet.session.origin + "/web?#menu_id=" + result[1];
                        }
                        self.ready.resolve();
                    });
                });
            }).fail(function() {
                self.load_stored_data();
                self.ready.reject();
            });
        },
        //TODO: Change name, save_activity or set_activity, this method is used in different context, like it is also used for set delete activity(rewrite)
        add_activity: function(data) {
            var activity_collection = this.get("activities");
            if(activity_collection.get(data.id)) {
                var activity_model = activity_collection.get(data.id);
                _.extend(activity_model, {id: data['id'], name: data['name'], task_id: data['task_id'], project_id: data['project_id'], unit_amount: data['unit_amount'], command: data['command']});
            } else {
                var activity = new project_timesheet.task_activity_model({project_timesheet_model: this, project_timesheet_db: this.project_timesheet_db}, {id: data['id'], name: data['name'], unit_amount: data['unit_amount'], date: data['date'], task_id: data['task_id'], project_id: data['project_id'], reference_id: data['reference_id'], command: data['command'], __last_update: data['__last_update'] });
                this.get('activities').add(activity);
            }
            this.project_timesheet_db.add_activity(data); //instead of data, use project.exportAsJson();
        },
        add_project: function(data) {
            //this method will create new object of model if data having virtual_id and add it into collection, then it will call add task for that collection model
            //It also finds project model from collection and add task in that model if project_id passed in data is already available
            //We can find model by id, coolection.get(id of model(e.g. id of project model)), id is magic attribute of model
            var projects_collection = this.get("projects");
            if(projects_collection.get(data.project_id[0])) {
                var project_model = projects_collection.get(data.project_id[0]);
                if (data.task_id && data.task_id.length) { 
                    project_model.add_task(data);
                }
            } else {
                var project = new project_timesheet.project_model({project_timesheet_model: this, project_timesheet_db: this.project_timesheet_db}, {id: data['project_id'][0], name: data['project_id'][1]});
                if (data.task_id && data.task_id.length) {
                    project.add_task(data);
                }
                this.get('projects').add(project);
            }
            //this.project_timesheet_db.add_activity(data); //instead of data, use project.exportAsJson();
        },
        name_search: function(term) {
            /*
            * This method searches into porjects collection and will return key,value pairs for projects.
            */
            var projects = this.get('projects');
            var search_result = [];
            var project_models = projects.models;
            for (var i = 0; i < project_models.length; i++) {
                search_result.push([project_models[i].id, project_models[i].name]);
            }
            if (term) {
                search_result = _.compact(_(search_result).map(function(x) {if (x[1].toLowerCase().contains(term.toLowerCase())) {return x;}}));
            }
            return search_result;
        },
        load_stored_data: function() {
            //We should simply call add_project method for activity_record which having project and task details, 
            //project model will call add_task, also check if project model is also available then will not create new model else create new model and push it into projects collection
            var self = this;
            var stored_activities = this.project_timesheet_db.load("activities");
            console.log("Inside load_stored_data ::: ", stored_activities);
            _.each(stored_activities, function(record) {
                self.add_activity(record);
                self.add_project(record);
            });
            this.project_timesheet_db.initialize_unique_id();
            this.project_timesheet_db.initialize_reference_sequence();
        },
        load_server_data: function() {
            var self = this;
            //Load last 30 days data and updated localstorage and then reload models(done by load_stored_data method)
            var momObj = new moment();
            var end_date = project_timesheet.datetime_to_str(momObj._d);
            var start_date = project_timesheet.datetime_to_str(momObj.subtract(30, "days")._d);
            /*
            return new project_timesheet.Model(project_timesheet.session, "project.task.work").call("search_read", {
                domain: [["date", ">=", start_date], ["date", "<=", end_date]],
                fields: ["id", "task_id", "name", "hours", "date"]
            }).then(function(work_activities) {
                var tasks = _.pluck(work_activities, "task_id");
                tasks = _.pluck(_.groupBy(tasks), 0);
                return new project_timesheet.Model(project_timesheet.session, "project.task").call("search_read", {
                    domain: [["id", "in", _.map(tasks, function(task) {return task[0];})]],
                    fields: ['id', 'project_id', "priority"]
                }).then(function(tasks_read) {
                    var projects = [];
                    //set project_id in activities, where task_id is projects.id
                    _.each(tasks_read, function(task) {
                        var activities = _.filter(work_activities, function(activity) {return activity.task_id[0] == task.id;});
                        _.each(activities, function(activity) {
                            activity['project_id'] = task['project_id'];
                            activity['priority'] = task['priority'];
                        });
                    });
                    self.project_timesheet_db.add_activities(work_activities);
                });
            })
            */
           return new project_timesheet.Model(project_timesheet.session, "hr.analytic.timesheet").call("load_data", {
               domain: [["date", ">=", start_date], ["date", "<=", end_date]],
               fields: ["id", "write_date", "create_date", "user_id", "task_id", "name", "unit_amount", "date", "account_id", 'reference_id', '__last_update']
           }).then(function(work_activities) {
               self.project_timesheet_db.add_activities(work_activities);
           }).promise();
        },
        //TO REMOVE: If not necessary
        set_screen_data: function(key,value){
            if(arguments.length === 2){
                this.screen_data[key] = value;
            }else if(arguments.length === 1){
                for(key in arguments[0]){
                    this.screen_data[key] = arguments[0][key];
                }
            }
        },
        //TO REMOVE: If not necessary
        //return screen data based on key passed
        get_screen_data: function(key){
            return this.screen_data[key];
        },
        check_session: function(){
            var self = this;
            if (_.isEmpty(this.project_timesheet_db.get_project_timesheet_session())) {
                return new project_timesheet.Model(project_timesheet.session, "project.timesheet.session").call("get_session", []).done(function(project_timesheet_session) {
                    self.project_timesheet_db.add_project_timesheet_session(project_timesheet_session);
                }).promise();
            }
        },
        save_to_server: function() {
            //TODO: Load model data in JSON format, check whether project is to create, task is to create, and activity is to create, write or delete
            //Once we done with data collection from model, save each record by calling project's create method, remove record from localstorage and then in last reload last 30 days data, that is call load_server_data
            //If record is failed in record creation then do not remove it from localstorage and keep it's state = pending'
            var self = this;
            this.defs = [];
            var defer = $.Deferred();
            var records = [];
            project_timesheet.blockUI();
            var generate_reference_id = function() { //May be move this function in db
                var project_timesheet_session = self.project_timesheet_db.get_project_timesheet_session();
                console.log("project_timesheet_session is ::: ", project_timesheet_session);
                console.log("Sequence ::: ", self.project_timesheet_db.sequence);
                return project_timesheet_session.session_id.toString() + "-" + project_timesheet_session.login_number.toString() + "-" + (self.project_timesheet_db.sequence+1);
            };
            console.log("stored project timesheet session is ::: ", this.project_timesheet_db.get_project_timesheet_session());
            $.when(self.check_session()).done(function(){
                var activity_collection = self.get('activities');
                var activity_models = activity_collection.models;
                for (var i = 0; i < activity_models.length; i++) {
                    var json_data = activity_models[i].export_as_JSON();
                    if (!_.isUndefined(json_data.command)) {
                        //If reference_id is not there then create unique Reference ID
                        if (!json_data.reference_id) {
                            //json_data['reference_id'] = json_data.user_id.toString() + json_data.project_id[0].toString() + json_data.date;
                            var reference_id = generate_reference_id();
                            _.extend(activity_models[i], {'reference_id': reference_id});
                            json_data['reference_id'] = reference_id;
                            self.project_timesheet_db.add_activity(json_data);
                        }
                        records.push(json_data);
                    }
                }
                //Load data domain sent in sync_data so that it returns fresh data of last 30 days
                var momObj = new moment();
                var end_date = project_timesheet.datetime_to_str(momObj._d);
                var start_date = project_timesheet.datetime_to_str(momObj.subtract(30, "days")._d);
                var load_data_domain = [["date", ">=", start_date], ["date", "<=", end_date]];
                self.defs.push(new project_timesheet.Model(project_timesheet.session, "hr.analytic.timesheet").call("sync_data", [records, load_data_domain]).then(function(result) {
                    console.log("11111111111111111", result);
                    self.sync_complete(result);
                }).always(function() {
                    project_timesheet.unblockUI();
                }));
                return $.when.apply($, self.defs).then(function() {
                    console.log("222222222222222222");
                    self.load_stored_data();
                    defer.resolve();
                });
            });
            return defer;
        },
        sync_complete: function(sync_result) {
            //This method will flush localstorage data once it has been sync
            //TODO: Remove project_timesheet_session and reload with new fetched session, if session is new then we should also start sequence from 0
            this.project_timesheet_db.flush_activities();
            this.project_timesheet_db.flush_project_timesheet_session();
            this.project_timesheet_db.initialize_reference_sequence();
            this.project_timesheet_db.add_activities(sync_result.activities);
        },
        get_pending_records: function() {
           return this.project_timesheet_db.get_pending_records();
        }
    });

}