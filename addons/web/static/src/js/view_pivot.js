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

instance.web.views.add('pivot', 'instance.web.PivotView');

instance.web.PivotView = instance.web.View.extend({
    template: 'PivotView',
    display_name: _lt('Pivot'),
    view_type: 'pivot',
    events: {
        'click .oe-opened': 'on_open_header_click',
        'click .oe-closed': 'on_closed_header_click',
        'click .o-field-menu': 'on_field_menu_selection',
    },

    init: function(parent, dataset, view_id, options) {
        this._super(parent, dataset, view_id, options);
        this.model = new instance.web.Model(dataset.model, {group_by_no_leaf: true});
        this.action_manager = parent.action_manager;

        this.$buttons = options.$buttons;
        this.fields = {};
        this.measures = {};
        this.groupable_fields = {};
        this.ready = false; // will be ready after the first do_search
        this.data_loaded = $.Deferred();

        this.row_groupbys = [];
        this.col_groupbys = [];
        this.active_measures = [];
        this.headers = {};
        this.cells = {};
        this.has_data = false;

        this.last_header_selected = null;
    },
    start: function () {
        this.$table_container = this.$('.o-pivot-table');

        var load_fields = this.model.call('fields_get', [])
                .then(this.prepare_fields.bind(this));

        return $.when(this._super(), load_fields).then(this.render_buttons.bind(this));
    },
    render_buttons: function () {
        var self = this;
        var context = {measures: _.pairs(_.omit(this.measures, '__count__'))};
        this.$buttons.html(QWeb.render('PivotView.buttons', context));
        this.$buttons.click(this.on_button_click.bind(this));
        context.measures.forEach(function (kv, index) {
            if (_.contains(self.active_measures, kv[0])) {
                self.$buttons.find('.oe-measure-list li').eq(index).addClass('selected');
            }
        });
        var another_ctx = {fields: _.pairs(this.groupable_fields)};
        this.$field_selection = this.$('.o-field-selection');
        this.$field_selection.html(QWeb.render('PivotView.FieldSelection', another_ctx));
        openerp.web.bus.on('click', self, function () {
            self.$field_selection.find('ul').hide();
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
            //noinspection FallThroughInSwitchStatementJS
            switch (field.attrs.type) {
            case 'measure':
                self.active_measures.push(name);
                break;
            case 'col':
                self.col_groupbys.push(name);
                break;
            default:
                if ('operator' in field.attrs) {
                    self.active_measures.push(name);
                    break;
                }
            case 'row':
                self.row_groupbys.push(name);
            }
        });
        if (!self.active_measures.length) {
            self.active_measures.push('__count__');
        }
    },
    prepare_fields: function (fields) {
        var self = this,
            groupable_types = ['many2one', 'char', 'boolean', 
                               'selection', 'date', 'datetime'];
        this.fields = fields;
        _.each(fields, function (field, name) {
            if ((name !== 'id') && (field.store === true)) {
                if (field.type === 'integer' || field.type === 'float') {
                    self.measures[name] = field;
                }
                if (_.contains(groupable_types, field.type)) {
                    self.groupable_fields[name] = field;
                }
            }
        });
        this.measures['__count__'] = {string: "Quantity", type: "integer"};
    },
    do_search: function (domain, context, group_by) {
        this.domain = domain;
        this.context = context;
        var col_groupbys = []; // to do: extract properly from context
        if (!this.ready) {
            this.row_groupbys = group_by.length ? group_by : this.row_groupbys;
            this.col_groupbys = col_groupbys.length ? col_groupbys : this.col_groupbys;
            this.ready = true;
            this.data_loaded = this.load_data();
        } else {
            this.row_groupbys = group_by;
            this.data_loaded = this.load_data();
            this.do_show();
        }
    },
    do_show: function () {
        this.data_loaded.done(this.display_table.bind(this));
    },
    on_button_click: function (event) {
        var $target = $(event.target);
        if ($target.hasClass('oe-pivot-flip')) {this.flip()};
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
        this.display_table();
    },
    on_closed_header_click: function (event) {
        var id = $(event.target).data('id');
        var $test = $(event.target);
        var pos = $test.position();
        this.last_header_selected = id;
        this.$field_selection.find('ul').css('top', pos.top + $test.parent().height() - 2);
        this.$field_selection.find('ul').css('left', pos.left + event.offsetX);
        this.$field_selection.find('ul').show();
        event.stopPropagation();
    },
    on_field_menu_selection: function (event) {
        var field = $(event.target).parent().data('field');
        this.expand_header(this.last_header_selected, field)
            .then(this.proxy('display_table'));
    },
    expand_header: function (header_id, field) {
        var self = this,
            header = this.headers[header_id];

        var other_root = header.root === this.main_row.root ? this.main_col.root : this.main_row.root,
            other_groupbys = header.root === this.main_row.root ? this.col_groupbys : this.row_groupbys,
            fields = [].concat(field, other_groupbys, this.active_measures),
            groupbys = [];

        for (var i = 0; i <= other_groupbys.length; i++) {
            groupbys.push([field].concat(other_groupbys.slice(0,i)));
        }
        return $.when.apply(null, groupbys.map(function (groupby) {
            return self.model.query(fields)
                .filter(header.domain)
                .context(self.context)
                .lazy(false)
                .group_by(groupby);
        })).then(function () {
            var data = Array.prototype.slice.call(arguments),
                datapt, attrs, j, k, l, row, col, cell_value;
            for (i = 0; i < data.length; i++) {
                for (j = 0; j < data[i].length; j++){
                    datapt = data[i][j];
                    attrs = datapt.attributes;
                    if (i === 0) attrs.value = [attrs.value];
                    for (k = 0; k < attrs.value.length; k++) {
                        attrs.value[k] = self.sanitize_value(attrs.value[k]);
                    }
                    if (i === 0) {
                        row = self.make_header(datapt, header.root, 0, 1, header);
                    } else {
                        row = self.get_header(datapt, header.root, 0, 1, header);
                    }
                    col = self.get_header(datapt, other_root, 1, i + 1);

                    for (cell_value = {}, l=0; l < self.active_measures.length; l++) {
                        cell_value[self.active_measures[l]] = attrs.aggregates[self.active_measures[l]];
                    }
                    self.cells[row.id] || (self.cells[row.id] = []);
                    cell_value['__count__'] = attrs.length;
                    self.cells[row.id][col.id] = cell_value;
                }
            }
        });
    },
    // returns a deferred that resolve when the data is loaded.
    load_data: function () {
        var self = this,
            i, j, 
            groupbys = [],
            row_gbs = this.row_groupbys,
            col_gbs = this.col_groupbys,
            fields = [].concat(row_gbs, col_gbs, this.active_measures);
        for (i = 0; i < row_gbs.length + 1; i++) {
            for (j = 0; j < col_gbs.length + 1; j++) {
                groupbys.push(row_gbs.slice(0,i).concat(col_gbs.slice(0,j)));
            }
        }
        return $.when.apply(null, groupbys.map(function (groupby) {
            return self.model.query(fields)
                .filter(self.domain)
                .context(self.context)
                .lazy(false)
                .group_by(groupby);
        })).then(self.prepare_data.bind(this));
    },
    prepare_data: function () {
        var i, j, k, l, m,
            index = 0,
            row_gbs = this.row_groupbys,
            col_gbs = this.col_groupbys,
            data = Array.prototype.slice.call(arguments),
            main_row_header, main_col_header,
            row, col, attrs, datapt, cell_value;

        for (i = 0; i < row_gbs.length + 1; i++) {
            for (j = 0; j < col_gbs.length + 1; j++) {
                for (k = 0; k < data[index].length; k++) {
                    datapt = data[index][k];
                    attrs = datapt.attributes;
                    if (i + j === 1) {
                        attrs.value = [attrs.value];
                    }
                    for (l = 0; l < attrs.value.length; l++) {
                        attrs.value[l] = this.sanitize_value(attrs.value[l]);
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
                    this.cells[row.id] || (this.cells[row.id] = []);
                    for (cell_value = {}, m=0; m < this.active_measures.length; m++) {
                        cell_value[this.active_measures[m]] = attrs.aggregates[this.active_measures[m]];
                    }
                    cell_value['__count__'] = attrs.length;
                    this.cells[row.id][col.id] = cell_value;
                }
                index++;
            }
        }
        this.main_row = { root: main_row_header };
        this.main_col = { root: main_col_header };
    },
    sanitize_value: function (value) {
        if (value === false) return _t("Undefined");
        if (value instanceof Array) return value[1];
        return value;
    },
    make_header: function (data_pt, root, i, j, parent_header) {
        var attrs = data_pt.attributes,
            value = attrs.value,
            title = value.length ? value[value.length - 1] : total;
        var path, parent;
        if (parent_header) {
            path = parent_header.path.concat(title);
            parent = parent_header;
        } else {
            path = [total].concat(value.slice(i,j-1)),
            parent = value.length? find_path_in_tree(root, path) : null;
        } 
        var header = {
            id: generate_id(),
            title: title,
            expanded: false,
            domain: data_pt.model._domain,
            children: [],
            path: value.length ? parent.path.concat(title) : [title]
        };
        this.headers[header.id] = header;
        header.root = root || header;
        if (parent) {
            parent.children.push(header);
            parent.expanded = true;
        }
        return header;
    },
    get_header: function (data_pt, root, i, j, parent) {
        var path;
        if (parent) {
            path = parent.path.concat(data_pt.attributes.value.slice(i,j));
        } else {
            path = [total].concat(data_pt.attributes.value.slice(i,j));
        }
        return find_path_in_tree(root, path);
    },
    display_table: function () {
        console.log('display_table');
        if (!this.active_measures.length || !this.has_data) {
            return this.$table_container.empty().append(QWeb.render('PivotView.nodata'));
        }
        var $fragment = $(document.createDocumentFragment()),
            $table = $('<table>')
                .addClass('table table-hover table-condensed')
                .appendTo($fragment),
            $thead = $('<thead>').appendTo($table),
            $tbody = $('<tbody>').appendTo($table),
            headers = this.compute_headers(),
            rows = this.compute_rows(),
            nbr_measures = this.active_measures.length,
            nbr_cols = (this.main_col.width === 1) ? nbr_measures : (this.main_col.width + 1)*nbr_measures;
        for (var i=0; i < nbr_cols + 1; i++) {
            $table.prepend($('<col>'));
        }
        this.draw_headers($thead, headers);
        this.draw_rows($tbody, rows);
        $table.on('hover', 'td', function () {
            $table.find('col:eq(' + $(this).index()+')').toggleClass('hover');
        });
        this.$table_container.empty().append($fragment);
    },
    draw_headers: function ($thead, headers) {
        var self = this,
            i, j, cell, $row, $cell,
            display_total = this.main_col.width > 1;

        var groupby_labels = _.map(this.col_groupbys, function (gb) {
            return self.groupable_fields[gb.split(':')[0]].string;
        });

        for (i = 0; i < headers.length; i++) {
            $row = $('<tr>');
            for (j = 0; j < headers[i].length; j++) {
                cell = headers[i][j];
                $cell = $('<th>')
                    .text(cell.title)
                    .attr('rowspan', cell.height)
                    .attr('colspan', cell.width);
                if (cell.total) {
                    $cell.addClass('oe-total');
                }
                if (i > 0) {
                    $cell.attr('title', groupby_labels[i-1]);
                }
                if (cell.expanded !== undefined) {
                    $cell.addClass(cell.expanded ? 'oe-opened' : 'oe-closed');
                    $cell.data('id', cell.id);
                }
                if (cell.measure) {
                    $cell.addClass('measure-row')
                        .text(cell.measure);
                    if (display_total && (j >= headers[i].length - this.active_measures.length)) {
                        $cell.addClass('oe-total');
                    }
                }
                $row.append($cell);
            }
            $thead.append($row);
        }
    },
    draw_rows: function ($tbody, rows) {
        var self = this,
            i, j, value, length, $row, $cell, $header,
            nbr_measures = this.active_measures.length,
            length = rows[0].values.length,
            display_total = this.main_col.width > 1;

        var groupby_labels = _.map(this.row_groupbys, function (gb) {
            return self.groupable_fields[gb.split(':')[0]].string;
        });
        var measure_types = this.active_measures.map(function (name) {
            return self.measures[name].type;
        });
        for (i = 0; i < rows.length; i++) {
            $row = $('<tr>');
            $header = $('<td>')
                .text(rows[i].title)
                .data('id', rows[i].id)
                .css('padding-left', (5 + rows[i].indent * 30) + 'px')
                .addClass(rows[i].expanded ? 'oe-opened' : 'oe-closed');
            if (rows[i].indent > 0) $header.attr('title', groupby_labels[rows[i].indent - 1]);
            $header.appendTo($row);
            for (j = 0; j < length; j++) {
                value = format_value(rows[i].values[j], {type: measure_types[j % nbr_measures]});
                $cell = $('<td>').text(value);
                if ((j >= length - this.active_measures.length) && display_total) {
                    $cell.css('font-weight', 'bold');   
                }
                $row.append($cell);
            }
            $tbody.append($row);
        }
    },
    compute_headers: function () {
        var self = this,
            main_col_dims = this.get_header_width_depth(this.main_col.root),
            depth = main_col_dims.depth,
            width = main_col_dims.width,
            nbr_measures = this.active_measures.length,
            result = [[{width:1, height: nbr_measures > 1 ? depth + 1: depth}]];
        this.main_col.width = width;
        traverse_tree(this.main_col.root, function (header) {
            var index = header.path.length - 1,
                cell = {
                    width: self.get_header_width(header) * nbr_measures,
                    height: header.expanded ? 1 : depth - index,
                    title: header.title,
                    id: header.id,
                    expanded: header.expanded,
                };
            if (result[index]) result[index].push(cell);
            else result[index] = [cell];
        });
        this.main_col.width = width;
        if (width > 1) {
            var total_cell = {width:nbr_measures, height: depth};
            if (nbr_measures === 1) {
                total_cell.title = this.measures[this.active_measures[0]].string;
                total_cell.total = true;
            };
            result[0].push(total_cell);
        }
        if (nbr_measures > 1) {
            var nbr_cols = width === 1 ? nbr_measures : (width + 1)*nbr_measures;
            for (var i = 0, measure_row = [], measure; i < nbr_cols; i++) {
                measure = this.active_measures[i % nbr_measures];
                measure_row.push({measure: this.measures[measure].string});
            }
            result.push(measure_row);
        }
        return result;
    },
    get_header_width: function (header) {
        var self = this;
        if (!header.children.length) return 1;
        if (!header.expanded) return 1;
        return header.children.reduce(function (s, c) {
            return s + self.get_header_width(c);
        }, 0);
    },
    get_header_width_depth: function (header) {
        var depth = 1,
            width = 0;
        traverse_tree (header, function (hdr) {
            depth = Math.max(depth, hdr.path.length);
            if (!hdr.expanded) width++;
        });
        return {width: width, depth: depth};
    },
    compute_rows: function () {
        var self = this,
            aggregates, i,
            result = [],
            nbr_measures = this.active_measures.length;
        traverse_tree(this.main_row.root, function (header) {
            var values = [];
            result.push({
                id: header.id,
                indent: header.path.length - 1,
                title: header.title,
                expanded: header.expanded,
                values: values,              
            });
            traverse_tree(self.main_col.root, add_cells, header.id, values);
            if (self.main_col.width > 1) {
                aggregates = self.get_value(header.id, self.main_col.root.id);
                for (i = 0; i < self.active_measures.length; i++) {
                    values.push(aggregates && aggregates[self.active_measures[i]]);
                }
            }
        });
        return result;
        function add_cells (col_hdr, row_id, values) {
            if (col_hdr.expanded) return;
            aggregates = self.get_value(row_id, col_hdr.id);
            for (i = 0; i < self.active_measures.length; i++) {
                values.push(aggregates && aggregates[self.active_measures[i]]);
            }
        }
    },
    get_value: function (id1, id2) {
        if (id1 in this.cells) return this.cells[id1][id2];
        else return this.cells[id2][id1];
    },
    flip: function () {
        var temp = this.main_col;
        this.main_col = this.main_row;
        this.main_row = temp;

        temp = this.row_groupbys;
        this.row_groupbys = this.col_groupbys;
        this.col_groupbys = temp;

        this.display_table();
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
});

// helpers
var id = -1;

function generate_id () {
    return ++id;
}

function traverse_tree(root, f, arg1, arg2) {
    f(root, arg1, arg2);
    if (!root.expanded) return;
    for (var i = 0; i < root.children.length; i++) {
        traverse_tree(root.children[i], f, arg1, arg2);
    }
}

function find_path_in_tree(root, path) {
    var i,
        l = root.path.length;
    if (l === path.length) {
        return (root.path[l-1] === path[l - 1]) ? root : null;
    }
    for (i = 0; i < root.children.length; i++) {
        if (root.children[i].path[l] === path[l]) {
            return find_path_in_tree(root.children[i], path);
        }
    }
    return null;
}

})();
