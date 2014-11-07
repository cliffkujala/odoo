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
        
        this.measures = [];
        this.active_measure = '__count__';
        this.groupbys = [];
        this.$buttons = options.$buttons;
    },
    start: function () {
        // this.$table_container = this.$('.o-pivot-table');

        var load_fields = this.model.call('fields_get', [])
                .then(this.prepare_fields.bind(this));

        return $.when(this._super(), load_fields).then(this.render_buttons.bind(this));
    },
    render_buttons: function () {
        // var self = this;
        var context = {measures: _.pairs(_.omit(this.measures, '__count__'))};
        this.$buttons.html(QWeb.render('GraphView.buttons', context));
        this.$measure_list = this.$buttons.find('.oe-measure-list');
        this.update_measure();
        this.$buttons.find('button').tooltip();
        // this.$buttons.click(this.on_button_click.bind(this));
        // context.measures.forEach(function (kv, index) {
        //     if (_.contains(self.active_measures, kv[0])) {
        //         self.$buttons.find('.oe-measure-list li').eq(index).addClass('selected');
        //     }
        // });
        // var another_ctx = {fields: _.pairs(this.groupable_fields)};
        // this.$field_selection = this.$('.o-field-selection');
        // this.$field_selection.html(QWeb.render('PivotView.FieldSelection', another_ctx));
        // openerp.web.bus.on('click', self, function () {
        //     self.$field_selection.find('ul').first().hide();
        // });
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
        this.data_loaded = this.load_data();
        // this.context = context;
        // if (!this.ready) {
        //     this.data_loaded = this.load_data(true);
        //     this.ready = true;
        //     return;
        // }
        // this.data_loaded = this.load_data(true);
        // return this.do_show();

        // var col_groupbys = []; // to do: extract properly from context
        // if (!this.ready) {
        //     this.row_groupbys = group_by.length ? group_by : this.row_groupbys;
        //     this.col_groupbys = col_groupbys.length ? col_groupbys : this.col_groupbys;
        //     this.ready = true;
        //     this.data_loaded = this.load_data();
        // } else {
        //     this.row_groupbys = group_by;
        //     this.data_loaded = this.load_data();
        //     this.do_show();
        // }
    },
    do_show: function () {
        this.data_loaded.done(this.display_graph.bind(this));
    },
    on_button_click: function (event) {
        var $target = $(event.target);
        if ($target.hasClass('oe-pivot-flip')) {this.flip();}
        if ($target.hasClass('oe-pivot-expand-all')) {this.expand_all();}
        if ($target.parents('.oe-measure-list').length) {
            var parent = $target.parent(),
                field = parent.data('field');
            parent.toggleClass('selected');
            event.stopPropagation();
            this.toggle_measure(field);
        }
    },
    on_open_header_click: function (event) {
        var id = $(event.target).data('id'),
            header = this.headers[id];
        header.expanded = false;        
        header.children = [];
        var new_groupby_length = this.get_header_depth(header.root) - 1;
        header.root.groupbys.splice(new_groupby_length);
        this.display_table();
    },
    on_closed_header_click: function (event) {
        var id = $(event.target).data('id'),
            header = this.headers[id],
            groupbys = header.root.groupbys;
        if (header.path.length - 1 < groupbys.length) {
            this.expand_header(header, groupbys[header.path.length - 1])
                .then(this.proxy('display_table'));
        } else {
            var $test = $(event.target);
            var pos = $test.position();
            this.last_header_selected = id;
            var $menu = this.$field_selection.find('ul').first();
            $menu.css('top', pos.top + $test.parent().height() - 2);
            $menu.css('left', pos.left + event.offsetX);
            $menu.show();
            event.stopPropagation();            
        }
    },

    // returns a deferred that resolve when the data is loaded.
    load_data: function () {
        return $.when();
        // var should_update = (update && this.main_row.root && this.main_col.root);
        // var self = this,
        //     i, j, 
        //     groupbys = [],
        //     row_gbs = this.main_row.groupbys,
        //     col_gbs = this.main_col.groupbys,
        //     fields = [].concat(row_gbs, col_gbs, this.active_measures);
        // for (i = 0; i < row_gbs.length + 1; i++) {
        //     for (j = 0; j < col_gbs.length + 1; j++) {
        //         groupbys.push(row_gbs.slice(0,i).concat(col_gbs.slice(0,j)));
        //     }
        // }
        // return $.when.apply(null, groupbys.map(function (groupby) {
        //     return self.model.query(fields)
        //         .filter(self.domain)
        //         .context(self.context)
        //         .lazy(false)
        //         .group_by(groupby);
        // })).then(function () {
        //     var data = Array.prototype.slice.call(arguments);
        //     self.prepare_data(data, should_update);
        // });
    },
    prepare_data: function (data, should_update) {
        var i, j, k, l, m,
            index = 0,
            row_gbs = this.main_row.groupbys,
            col_gbs = this.main_col.groupbys,
            main_row_header, main_col_header,
            row, col, attrs, datapt, cell_value,
            field;

        for (i = 0; i < row_gbs.length + 1; i++) {
            for (j = 0; j < col_gbs.length + 1; j++) {
                for (k = 0; k < data[index].length; k++) {
                    datapt = data[index][k];
                    attrs = datapt.attributes;
                    if (i + j === 1) {
                        attrs.value = [attrs.value];
                    }
                    for (l = 0; l < attrs.value.length; l++) {
                        if (l < i) field = row_gbs[l];
                        else field = col_gbs[l - i];
                        attrs.value[l] = this.sanitize_value(attrs.value[l], field);
                    }
                    if (j === 0) {
                        row = this.make_header(datapt, main_row_header, 0, i);
                    } else {
                        row = this.get_header(datapt, main_row_header, 0, i);
                    }
                    if (i === 0) {
                        col = this.make_header(datapt, main_col_header, i, i+j);
                    } else {
                        col = this.get_header(datapt, main_col_header, i, i+j);
                    }
                    if (i + j === 0) {
                        this.has_data = attrs.length > 0;
                        main_row_header = row;
                        main_col_header = col;
                    }
                    if (!this.cells[row.id]) this.cells[row.id] = [];
                    for (cell_value = {}, m=0; m < this.active_measures.length; m++) {
                        cell_value[this.active_measures[m]] = attrs.aggregates[this.active_measures[m]];
                    }
                    cell_value.__count__ = attrs.length;
                    this.cells[row.id][col.id] = cell_value;
                }
                index++;
            }
        }
        if (should_update) {
            this.update_tree(this.main_row.root, main_row_header);
            var new_groupby_length = this.get_header_depth(main_row_header) - 1;
            main_row_header.groupbys = this.main_row.root.groupbys.slice(0, new_groupby_length);
            this.update_tree(this.main_col.root, main_col_header);
            new_groupby_length = this.get_header_depth(main_col_header) - 1;
            main_col_header.groupbys = this.main_col.root.groupbys.slice(0, new_groupby_length);
        } else {
            main_row_header.groupbys = this.main_row.groupbys;
            main_col_header.groupbys = this.main_col.groupbys;
        }
        main_row_header.other_root = main_col_header;
        main_col_header.other_root = main_row_header;
        this.main_row.root = main_row_header;
        this.main_col.root = main_col_header;
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
    display_graph: function () {

    },
});

// helpers
var id = -1;

function generate_id () {
    return ++id;
}

})();
