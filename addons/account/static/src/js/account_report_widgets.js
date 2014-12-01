(function () {
    'use strict';

    $(document).ready(function() {
        openerp.footnote = {};
        var _t = openerp._t;



        openerp.reportWidgets = openerp.Widget.extend({
            events: {
                'click .annotable': 'addFootNote',
                'click .foldable': 'fold',
                'click .unfoldable': 'unfold',
                'click .saveFootNote': 'saveFootNote',
            },
            start: function() {
                this.footNoteSeqNum = 1;
                return this._super();
            },
            addFootNote: function(e) {
                e.preventDefault();
                if ($(e.target).find("sup").length == 0) {
                    $(e.target).append(' <sup>' + this.footNoteSeqNum + '</sup>');
                    this.$("table").after('<div class="row mt32 mb32"><label for="footnote' + 
                        this.footNoteSeqNum + '">' + this.footNoteSeqNum + '</label><textarea name="footnote' + this.footNoteSeqNum + 
                        '" rows=4 class="form-control">Insert foot note here</textarea><button class="btn btn-primary saveFootNote">Save</button></div>');
                    this.footNoteSeqNum++;
                }
            },
            fold: function(e) {
                e.preventDefault();
                var level = $(e.target).next().html().length
                var el;
                var $el;
                var $nextEls = $(e.target).parent().parent().nextAll();
                for (el in $nextEls) {
                    $el = $($nextEls[el]).find("td span.level");
                    if ($el.html() == undefined)
                        break;
                    if ($el.html().length > level){
                        $el.parent().parent().hide();
                    }
                    else {
                        break;
                    }
                }
                $(e.target).replaceWith('<span class="unfoldable">^</span>');
            },
            unfold: function(e) {
                e.preventDefault();
                var level = $(e.target).next().html().length
                var el;
                var $el;
                var $nextEls = $(e.target).parent().parent().nextAll();
                for (el in $nextEls) {
                    $el = $($nextEls[el]).find("td span.level");
                    if ($el.html() == undefined)
                        break;
                    if ($el.html().length > level){
                        $el.parent().parent().show();
                    }
                    else {
                        break;
                    }
                }
                $(e.target).replaceWith('<span class="foldable">&gt;</span>');                
            },
            saveFootNote: function(e) {
                e.preventDefault();
                var num = $(e.target).parent().find("label").text();
                var note = $(e.target).parent().find("textarea").val();
                $(e.target).parent().replaceWith('<div class="row mt32 mb32">' + num + '. ' + note + '</div>')
            }
        });
        var reportWidgets = new openerp.reportWidgets();
        reportWidgets.setElement($('.oe_account_report_widgets'));
        reportWidgets.start();
    });

})();