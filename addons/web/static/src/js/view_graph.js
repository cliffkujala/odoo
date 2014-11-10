/*---------------------------------------------------------
 * Odoo Pivot Table view
 *---------------------------------------------------------*/

(function () {
'use strict';

var instance = openerp,
    _lt = instance.web._lt,
    _t = instance.web._t,
    QWeb = instance.web.qweb,
    format_value = instance.web.format_value,
    total = _t("Total");

instance.web.views.add('graph', 'instance.web.GraphView');

instance.web.GraphView = instance.web.View.extend({
    template: 'GraphView',
    display_name: _lt('Graph'),
    view_type: 'graph',

    init: function(parent, dataset, view_id, options) {
        this._super(parent, dataset, view_id, options);
        this.model = new instance.web.Model(dataset.model, {group_by_no_leaf: true});

        this.ready = false;
        this.mode = "bar";
        this.measures = [];
        this.active_measure = '__count__';
        this.groupbys = [];
        this.data = [];
        this.$buttons = options.$buttons;
    },
    start: function () {
        var load_fields = this.model.call('fields_get', [])
                .then(this.prepare_fields.bind(this));

        return $.when(this._super(), load_fields).then(this.render_buttons.bind(this));
    },
    render_buttons: function () {
        var context = {measures: _.pairs(_.omit(this.measures, '__count__'))};
        this.$buttons.html(QWeb.render('GraphView.buttons', context));
        this.$measure_list = this.$buttons.find('.oe-measure-list');
        this.update_measure();
        this.$buttons.find('button').tooltip();
        this.$buttons.click(this.on_button_click.bind(this));
    },
    update_measure: function () {
        var self = this;
        this.$measure_list.find('li').each(function (index, li) {
            $(li).toggleClass('selected', $(li).data('field') === self.active_measure);
        });
    },
    view_loading: function (fvg) {
        var self = this;
        this.do_push_state({});
        fvg.arch.children.forEach(function (field) {
            var name = field.attrs.name;
            if (field.attrs.interval) {
                name += ':' + field.attrs.interval;
            }
            switch (field.attrs.type) {
            case 'measure':
                self.active_measure = name;
                break;
            case 'col':
            case 'row':
                self.groupbys.push(name);
                break;
            }
        });
        console.log(self.groupbys);
    },
    prepare_fields: function (fields) {
        var self = this;
        this.fields = fields;
        _.each(fields, function (field, name) {
            if ((name !== 'id') && (field.store === true)) {
                if (field.type === 'integer' || field.type === 'float') {
                    self.measures[name] = field;
                }
            }
        });
        this.measures.__count__ = {string: "Quantity", type: "integer"};
    },
    do_search: function (domain, context, group_by) {
        // if (_.isEqual(domain, this.domain)) return;
        this.domain = domain;
        this.context = context;
        if (!this.ready) {
            this.data_loaded = this.load_data();
            this.ready = true;
            return;
        }
        this.groupbys = group_by;
        this.data_loaded = this.load_data();
        return this.do_show();
    },
    do_show: function () {
        this.data_loaded.done(this.display_graph.bind(this));
    },
    on_button_click: function (event) {
        var $target = $(event.target);
        if ($target.hasClass('oe-bar-mode')) {this.switch_mode('bar');}
        if ($target.hasClass('oe-line-mode')) {this.switch_mode('line');}
        if ($target.hasClass('oe-pie-mode')) {this.switch_mode('pie');}
        if ($target.parents('.oe-measure-list').length) {
            var parent = $target.parent(),
                field = parent.data('field');
            this.active_measure = field;
            parent.toggleClass('selected');
            event.stopPropagation();
            this.update_measure();
            this.load_data().then(this.proxy('display_graph'));
        }
    },
    // returns a deferred that resolve when the data is loaded.
    load_data: function () {
        console.log('loading_data', this.groupbys, this.active_measure);
        var fields = this.groupbys.concat(this.active_measure);
        return this.model
                    .query(fields)
                    .filter(this.domain)
                    .context(this.context)
                    .lazy(false)
                    .group_by(this.groupbys)
                    .then(this.proxy('prepare_data'));
    },
    prepare_data: function () {
        console.log('prepare_data', arguments[0]);
        var raw_data = arguments[0];
        var data_pt, j, values;

        this.data = [];
        for (var i = 0; i < raw_data.length; i++) {
            data_pt = raw_data[i].attributes;
            console.log(data_pt);
            values = [];
            for (j = 0; j < data_pt.value.length; j++) {
                values[j] = this.sanitize_value(data_pt.value[j], data_pt.grouped_on[j]);
            }
            this.data.push({
                labels: values,
                value: data_pt.aggregates[this.active_measure]
            });
        }
    },
    sanitize_value: function (value, field) {
        if (value === false) return _t("Undefined");
        if (value instanceof Array) return value[1];
        if (field && this.fields[field] && (this.fields[field].type === 'selection')) {
            var selected = _.where(this.fields[field].selection, {0: value})[0];
            return selected ? selected[1] : value;
        }
        return value;
    },
    toggle_measure: function (field) {
        if (_.contains(this.active_measures, field)) {
            this.active_measures = _.without(this.active_measures, field);
            this.display_table();
        } else {
            this.active_measures.push(field);            
            this.load_data().then(this.display_table.bind(this));
        }
    },
    switch_mode: function (mode) {
        this.mode = mode;
        console.log('switch_mode', mode);
    },
    display_graph: function () {
        console.log('display_graph');
    },
});


})();
