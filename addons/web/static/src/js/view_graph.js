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

nv.dev = false;  // sets nvd3 library in production mode

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
        this.initial_groupbys = [];
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
            default:
                self.initial_groupbys.push(name);
                break;
            }
        });
        self.groupbys = self.initial_groupbys.slice(0);
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
        this.groupbys = group_by.length ? group_by : this.initial_groupbys.slice(0);
        this.domain = domain;
        this.context = context;
        if (!this.ready) {
            this.data_loaded = this.load_data();
            this.ready = true;
            return;
        }
        this.data_loaded = this.load_data();
        return this.do_show();
    },
    do_show: function () {
        var self = this;
        this.data_loaded.done(function () {
            self.display_graph(); 
            self.$el.show();
        });
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
        var fields = this.groupbys;
        if (this.active_measure !== '__count__')
            fields = fields.concat(this.active_measure);
        return this.model
                    .query(fields)
                    .filter(this.domain)
                    .context(this.context)
                    .lazy(false)
                    .group_by(this.groupbys.slice(0,2))
                    .then(this.proxy('prepare_data'));
    },
    prepare_data: function () {
        var raw_data = arguments[0],
            is_count = this.active_measure === '__count__';
        var data_pt, j, values, value;

        this.data = [];
        for (var i = 0; i < raw_data.length; i++) {
            data_pt = raw_data[i].attributes;
            values = [];
            if (this.groupbys.length === 1) data_pt.value = [data_pt.value];
            for (j = 0; j < data_pt.value.length; j++) {
                values[j] = this.sanitize_value(data_pt.value[j], data_pt.grouped_on[j]);
            }
            value = is_count ? data_pt.length : data_pt.aggregates[this.active_measure];
            this.data.push({
                labels: values,
                value: value
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
        this.display_graph();
    },
    display_graph: function () {
        if (this.to_remove) {
            nv.utils.offWindowResize(this.to_remove);
        }
        this.$el.empty();
        this['display_' + this.mode]();
    },
    display_bar: function () {
        // prepare data for bar chart
        var data, values,
            measure = this.measures[this.active_measure].string;
        // zero groupbys
        if (this.groupbys.length === 0) {
            data = [{
                values: [{
                    x: this.ViewManager.title, 
                    y: this.data[0].value}],
                key: measure
            }];
        } 
        // one groupby
        if (this.groupbys.length === 1) {
            values = this.data.map(function (datapt) {
                return {x: datapt.labels, y: datapt.value};
            });
            data = [
                {
                    values: values,
                    key: measure,
                }
            ];
        }
        if (this.groupbys.length > 1) {
            var xlabels = [],
                series = [],
                label, serie, value;
            values = {};
            for (var i = 0; i < this.data.length; i++) {
                label = this.data[i].labels[0];
                serie = this.data[i].labels[1];
                value = this.data[i].value;
                if ((!xlabels.length) || (xlabels[xlabels.length-1] !== label)) {
                    xlabels.push(label);
                }
                series.push(this.data[i].labels[1]);
                if (!(serie in values)) {values[serie] = {};}
                values[serie][label] = this.data[i].value;
            }
            series = _.uniq(series);
            data = [];
            var current_serie, j;
            for (i = 0; i < series.length; i++) {
                current_serie = {values: [], key: series[i]};
                for (j = 0; j < xlabels.length; j++) {
                    current_serie.values.push({
                        x: xlabels[j],
                        y: values[series[i]][xlabels[j]] || 0,
                    });
                }
                data.push(current_serie);
            }
        }
        var svg = d3.select(this.$el[0]).append('svg');
        svg.datum(data);

        svg.transition().duration(0);

        var chart = nv.models.multiBarChart();
        chart.options({
          delay: 250,
          transitionDuration: 10,
          showLegend: true,
          showXAxis: true,
          showYAxis: true,
          rightAlignYAxis: false,
          stacked: true,
          reduceXTicks: false,
          // rotateLabels: 40,
          showControls: (this.groupbys.length > 1)
        });

        chart(svg);
        this.to_remove = chart.update;
        nv.utils.onWindowResize(chart.update);
    },
    display_pie: function () {
        var self = this,
            data = [],
            tickValues,
            tickFormat,
            measure = this.measures[this.active_measure].string;
        if (this.groupbys.length) {
            data = this.data.map(function (datapt) {
                return {x:datapt.labels.join("/"), y: datapt.value};
            });
        }
        var svg = d3.select(this.$el[0]).append('svg');
        svg.datum(data);

        svg.transition().duration(100);

        var chart = nv.models.pieChart();
        chart.options({
          delay: 250,
          transitionDuration: 100,
          color: d3.scale.category10().range(),
        });

        chart(svg);
        this.to_remove = chart.update;
        nv.utils.onWindowResize(chart.update);

    },
    display_line: function () {
        var self = this,
            data = [],
            tickValues,
            tickFormat,
            measure = this.measures[this.active_measure].string;
        if (this.groupbys.length === 1) {
            var values = this.data.map(function (datapt, index) {
                console.log(datapt);
                return {x: index, y: datapt.value};
            });
            data = [
                {
                    values: values,
                    key: measure,
                }
            ];
            tickValues = this.data.map(function (d, i) { return i;});
            tickFormat = function (d) {return self.data[d].labels;};
        }
        if (this.groupbys.length > 1) {
            data = [];
            var data_dict = {},
                tick = 0,
                tickLabels = [],
                serie, tickLabel,
                identity = function (p) {return p;};
            tickValues = [];
            for (var i = 0; i < this.data.length; i++) {
                if (this.data[i].labels[0] !== tickLabel) {
                    tickLabel = this.data[i].labels[0];
                    tickValues.push(tick);
                    tickLabels.push(tickLabel);
                    tick++;
                }
                serie = this.data[i].labels[1];
                if (!data_dict[serie]) {
                    data_dict[serie] = {
                        values: [],
                        key: serie,
                    };
                }
                data_dict[serie].values.push({
                    x: tick, y: this.data[i].value,
                });
                data = _.map(data_dict, identity);
            }
            tickFormat = function (d) {return tickLabels[d];};
        }

        var svg = d3.select(this.$el[0]).append('svg');
        svg.datum(data);

        svg.transition().duration(0);

        var chart = nv.models.lineChart();
        chart.options({
          margin: {left: 50, right: 50},
          useInteractiveGuideline: true,
          showLegend: true,
          showXAxis: true,
          showYAxis: true,
        });
        chart.xAxis.tickValues(tickValues)
            .tickFormat(tickFormat);

        chart(svg);
        this.to_remove = chart.update;
        nv.utils.onWindowResize(chart.update);  
    },
    destroy: function () {
        nv.utils.offWindowResize(this.to_remove);
        return this._super();
    }
});


// monkey patch nvd3 to allow removing eventhandler on windowresize events
// see https://github.com/novus/nvd3/pull/396 for more details

// Adds a resize listener to the window.
nv.utils.onWindowResize = function(fun) {
    if (fun === null) return;
    window.addEventListener('resize', fun);
};

// Backwards compatibility with current API.
nv.utils.windowResize = nv.utils.onWindowResize;

// Removes a resize listener from the window.
nv.utils.offWindowResize = function(fun) {
    if (fun === null) return;
    window.removeEventListener('resize', fun);
};

})();
