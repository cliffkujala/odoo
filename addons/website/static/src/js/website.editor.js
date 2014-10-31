(function () {
    'use strict';

    var website = openerp.website;
    var _t = openerp._t;

    //////////////////////////////////////////////////////////////////////////////////////////////////////////
    /* Summernote Lib (neek hack to make accessible: method and object) */

    var agent = $.summernote.objects.agent;
    var func = $.summernote.objects.func;
    var list = $.summernote.objects.list;
    var dom = $.summernote.objects.dom;
    var settings = $.summernote.objects.settings;
    var async = $.summernote.objects.async;
    var key = $.summernote.objects.key;
    var Style = $.summernote.objects.Style;
    var range = $.summernote.objects.range;
    var Table = $.summernote.objects.Table;
    var Editor = $.summernote.objects.Editor;
    var History = $.summernote.objects.History;
    var Button = $.summernote.objects.Button;
    var Toolbar = $.summernote.objects.Toolbar;
    var Popover = $.summernote.objects.Popover;
    var Handle = $.summernote.objects.Handle;
    var Dialog = $.summernote.objects.Dialog;
    var EventHandler = $.summernote.objects.EventHandler;
    var Renderer = $.summernote.objects.Renderer;
    var eventHandler = $.summernote.objects.eventHandler;
    var renderer = $.summernote.objects.renderer;

    //////////////////////////////////////////////////////////////////////////////////////////////////////////
    /* update and change the popovers content, and add history button */

    var fn_handle_update = eventHandler.handle.update;
    eventHandler.handle.update = function ($handle, oStyle, isAirMode) {
        fn_handle_update.call(this, $handle, oStyle, isAirMode);
        $handle.find('.note-control-selection').hide();
    };
    function summernote_popover_update ($popover) {
        var $imagePopover = $popover.find('.note-image-popover');
        var $linkPopover = $popover.find('.note-link-popover');
        var $airPopover = $popover.find('.note-air-popover');

        //////////////// image popover

        // add center button for images
        var $centerbutton = $(renderer.tplIconButton('fa fa-align-center', {
                title: _t('Center'),
                event: 'floatMe',
                value: 'center'
            })).insertAfter('[data-event="floatMe"][data-value="left"]');
        $imagePopover.find('button[data-event="removeMedia"]').parent().remove();
        $imagePopover.find('button[data-event="floatMe"][data-value="none"]').remove();

        // padding button
        var $padding = $('<div class="btn-group"/>');
        $padding.insertBefore($imagePopover.find('.btn-group:first'));
        var $button = $(renderer.tplIconButton('fa fa-plus-square-o', {
                title: _t('Padding'),
                dropdown: true
            })).appendTo($padding);
        var $ul = $('<ul class="dropdown-menu"/>').insertAfter($button);
        $ul.append('<li><a data-event="padding" href="#" data-value="">'+_t('None')+'</a></li>');
        $ul.append('<li><a data-event="padding" href="#" data-value="small">'+_t('Small')+'</a></li>');
        $ul.append('<li><a data-event="padding" href="#" data-value="medium">'+_t('Medium')+'</a></li>');
        $ul.append('<li><a data-event="padding" href="#" data-value="large">'+_t('Large')+'</a></li>');
        $ul.append('<li><a data-event="padding" href="#" data-value="xl">'+_t('xl')+'</a></li>');

        // padding button
        var $imageprop = $('<div class="btn-group"/>');
        $imageprop.appendTo($imagePopover.find('.popover-content'));
        $(renderer.tplIconButton('fa fa-picture-o', {
                title: _t('Edit'),
                event: 'showImageDialog'
            })).appendTo($imageprop);
        $(renderer.tplIconButton('fa fa-trash-o', {
                title: _t('Remove'),
                event: 'delete'
            })).appendTo($imageprop);

        $imagePopover.find('.popover-content').append($airPopover.find(".note-history").clone());
        
        //////////////// link popover

        $linkPopover.find('.popover-content').append($airPopover.find(".note-history").clone());

        //////////////// text/air popover

        var $para = $airPopover.find(".note-para");
        var $parent = $('<div class="note-ul btn-group"/>').insertBefore($para);
        var $button = $(renderer.tplIconButton('fa fa-list-ul', {
                title: _t('List'),
                dropdown: true
            }))
            .appendTo($parent);
        var $div = $('<div class="dropdown-menu"><div class="note-li btn-group"/></div>').insertAfter($button);
        $para.find('[data-event="insertUnorderedList"]').appendTo($div.children());
        $para.find('[data-event="insertOrderedList"]').appendTo($div.children());
        $para.find('div.note-list').appendTo($div);

        var $color = $airPopover.find('.note-color');
        var html = openerp.qweb.render('website.colorpicker');
        $color.find('.note-color-palette').prepend(html);
        var $bg = $color.find('.colorpicker:first button');
        var $fore = $color.find('.colorpicker:last button');

        $bg.each(function () { $(this).attr('data-event', 'backColor').attr('data-value', $(this).attr('class')); });
        $fore.each(function () { $(this).attr('data-event', 'foreColor').attr('data-value', $(this).attr('class').replace(/bg-/, 'text-')); });

        //// highlight the text format

        $airPopover.find('.note-style').on('mousedown', function () {
            var $format = $airPopover.find('[data-event="formatBlock"]');
            var r = range.create();
            var node = r.sc;
            var formats = $format.map(function () { return $(this).data("value"); }).get();
            while (node && (!node.tagName || (!node.tagName || formats.indexOf(node.tagName.toLowerCase()) === -1))) {
                node = node.parentNode;
            }
            $format.parent().removeClass('active');
            $format.filter('[data-value="'+node.tagName.toLowerCase()+'"]')
                .parent().addClass("active");
        });

        //////////////// tooltip

        $airPopover.add($linkPopover).add($imagePopover).find("button")
            .tooltip('destroy')
            .tooltip({
                container: 'body',
                trigger: 'hover',
                placement: 'bottom'
            }).on('click', function () {$(this).tooltip('hide');});
    }
    var fn_boutton_update = eventHandler.popover.button.update;
    eventHandler.popover.button.update = function ($container, oStyle) {
        fn_boutton_update.call(this, $container, oStyle);

        $container.find('[data-event]').parent().removeClass("active");

        $container.find('a[data-event="padding"][data-value="small"]').parent().toggleClass("active", $(oStyle.image).hasClass("padding-small"));
        $container.find('a[data-event="padding"][data-value="medium"]').parent().toggleClass("active", $(oStyle.image).hasClass("padding-medium"));
        $container.find('a[data-event="padding"][data-value="large"]').parent().toggleClass("active", $(oStyle.image).hasClass("padding-large"));
        $container.find('a[data-event="padding"][data-value="xl"]').parent().toggleClass("active", $(oStyle.image).hasClass("padding-xl"));
        $container.find('a[data-event="padding"][data-value=""]').parent().toggleClass("active", !$container.find('.active a[data-event="padding"]').length);

        $container.find('button[data-event="resize"][data-value="1"]').toggleClass("active", $(oStyle.image).hasClass("img-responsive"));
        $container.find('button[data-event="resize"][data-value="0.5"]').toggleClass("active", $(oStyle.image).hasClass("img-responsive-50"));
        $container.find('button[data-event="resize"][data-value="0.25"]').toggleClass("active", $(oStyle.image).hasClass("img-responsive-25"));

        $container.find('button[data-event="floatMe"][data-value="left"]').toggleClass("active", $(oStyle.image).hasClass("pull-left"));
        $container.find('button[data-event="floatMe"][data-value="center"]').toggleClass("active", $(oStyle.image).hasClass("center-block"));
        $container.find('button[data-event="floatMe"][data-value="right"]').toggleClass("active", $(oStyle.image).hasClass("pull-right"));
    };
    var fn_popover_update = eventHandler.popover.update;
    eventHandler.popover.update = function ($popover, oStyle, isAirMode) {
        var $imagePopover = $popover.find('.note-image-popover');
        var $linkPopover = $popover.find('.note-link-popover');
        var $airPopover = $popover.find('.note-air-popover');

        fn_popover_update.call(this, $popover, oStyle, isAirMode);

        if (!$popover.data('loaded')) {
            summernote_popover_update ($popover);
            $popover.data('loaded', true);
        }

        $popover.find('button[data-event="undo"]').attr('disabled', !history.hasUndo());
        $popover.find('button[data-event="redo"]').attr('disabled', !history.hasRedo());

        if (oStyle.range.sc.tagName === "IMG") {
            oStyle.image = oStyle.range.sc;
        }

        if (oStyle.image) {
            if (oStyle.image.parentNode.className.match(/(^|\s)media_iframe_video(\s|$)/i)) {
                oStyle.image = oStyle.image.parentNode;
            }
            $imagePopover.show();
            range.create(oStyle.image,0,oStyle.image,0).select();
        }

        if (oStyle.anchor && (!oStyle.range.isCollapsed() || (oStyle.range.sc.tagName && !dom.isAnchor(oStyle.range.sc)) || (oStyle.image && !$(oStyle.image).closest('a').length))) {
            $linkPopover.hide();
            oStyle.anchor = false;
        }

        if (oStyle.image || oStyle.anchor || !$(oStyle.range.sc).closest('.note-editable').length) {
            $airPopover.hide();
        } else {
            $airPopover.show();
        }
    };

    $(document).on('click keyup', function () {
        $('button[data-event="undo"]').attr('disabled', !history.hasUndo());
        $('button[data-event="redo"]').attr('disabled', !history.hasRedo());
    });

    eventHandler.editor.undo = function ($popover) {
        if(!$popover.attr('disabled')) history.undo();
        return false;
    };
    eventHandler.editor.redo = function ($popover) {
        if(!$popover.attr('disabled')) history.redo();
        return false;
    };

    //////////////////////////////////////////////////////////////////////////////////////////////////////////
    /* hack for image and link editor */

    eventHandler.editor.padding = function ($editable, sValue, $target) {
        var paddings = "small medium large xl".split(/\s+/);
        $editable.data('NoteHistory').recordUndo($editable);
        if (sValue.length) {
            paddings.splice(paddings.indexOf(sValue),1);
            $target.toggleClass('padding-'+sValue);
        }
        $target.removeClass("padding-" + paddings.join(" padding-"));
        setTimeout(function () { $target.trigger("mouseup"); },0);
        return false;
    };
    eventHandler.editor.resize = function ($editable, sValue, $target) {
        $editable.data('NoteHistory').recordUndo($editable);
        switch (+sValue) {
            case 1: $target.toggleClass('img-responsive').removeClass('img-responsive-50 img-responsive-25'); break;
            case 0.5: $target.toggleClass('img-responsive-50').removeClass('img-responsive img-responsive-25'); break;
            case 0.25: $target.toggleClass('img-responsive-25').removeClass('img-responsive img-responsive-50'); break;
        }
        setTimeout(function () { $target.trigger("mouseup"); },0);
        return false;
    };
    eventHandler.editor.floatMe = function ($editable, sValue, $target) {
        $editable.data('NoteHistory').recordUndo($editable);
        switch (sValue) {
            case 'center': $target.toggleClass('center-block').removeClass('pull-right pull-left'); break;
            case 'left': $target.toggleClass('pull-left').removeClass('pull-right center-block'); break;
            case 'right': $target.toggleClass('pull-right').removeClass('pull-left center-block'); break;
        }
        setTimeout(function () { $target.trigger("mouseup"); },0);
        return false;
    };

    eventHandler.dialog.showLinkDialog = function ($editable, $dialog, linkInfo) {
        var editor = new website.editor.LinkDialog($editable, linkInfo);
        editor.appendTo(document.body);

        var def = new $.Deferred();
        editor.on("save", this, function (linkInfo) {
            def.resolve(linkInfo);
            $('.note-popover .note-link-popover').show();
        });
        editor.on("cancel", this, function () { def.reject(); });
        return def;
    };
    var fn_editor_createLink = eventHandler.editor.createLink;
    eventHandler.editor.createLink = function ($editable, linkInfo, options) {
        var a = fn_editor_createLink.call(this, $editable, linkInfo, options);
        $(a).attr("class", linkInfo.className);
        return false;
    };
    eventHandler.dialog.showImageDialog = function ($editable) {
        var r = range.create();
        var editor = new website.editor.MediaDialog($editable, dom.isImg(r.sc) ? r.sc : null);
        editor.appendTo(document.body);
        return new $.Deferred().reject();
    };

    dom.isImg = function (node) {
        return node && (node.nodeName === "IMG" ||
            (node.nodeName === "SPAN" && node.className.match(/(^|\s)fa(-|\s|$)/i)) ||
            (node.className && node.className.match(/(^|\s)media_iframe_video(\s|$)/i)) ||
            (node.parentNode.className && node.parentNode.className.match(/(^|\s)media_iframe_video(\s|$)/i)) );
    };

    //////////////////////////////////////////////////////////////////////////////////////////////////////////
    /* attach event to Summernote
    * paste:
    *  - change the default feature of contentEditable
    * mousedown:
    *  - re-active snippet and carret
    *  - display editor popover
    */

    function reRangeSelect (event) {
        var r = range.create();
        if (!r || r.isCollapsed()) return;

        // check if the user move the caret on up or down
        var ref = false;
        var node = r.sc;
        var parent = r.ec.parentNode;
        while (node) {
            if (parent === node) {
                break;
            }
            if(event.target === node || event.target.parentNode === node) { /*check parent node for image, iframe and tag without child text node*/
                ref = true;
                break;
            }
            node = node.parentNode;
        }

        var data = range.reRange(r.sc, r.so, r.ec, r.eo, ref);

        if (data.sc !== r.sc || data.so !== r.so || data.ec !== r.ec || data.eo !== r.eo) {
            setTimeout(function () {
                data.select();
            },0);
        }

        $(data.sc).closest('.o_editable').data('range', r);
        return r;
    }
    var cursor_mousedown;
    function summernote_mouseup (event) {
        if ($(event.target).closest("#website-top-navbar, .note-popover").length) {
            return;
        }
        // don't rerange if simple click
        if (!cursor_mousedown || 10 < Math.pow(cursor_mousedown.clientX-event.clientX, 2)+Math.pow(cursor_mousedown.clientY-event.clientY, 2) ) {
            reRangeSelect(event);
        }
    }
    function summernote_mousedown (event) {
        history.splitNext();

        cursor_mousedown = event;
        var $btn = $(event.target).closest('.note-popover');
        if ($btn.length) {
            var r = range.create();
            if (r) {
              $(document).one('mouseup', function () {
                setTimeout(function () {
                    r = range.create() || r;
                    var node = r.sc.tagName ? r.sc : r.sc.parentNode;
                    $(node).trigger("mouseup");
                    setTimeout(function () {
                        r.select();
                        $(node).trigger("keydown");
                    },0);
                },0);
              });
            }
        }
    }
    function summernote_click (event) {
        if (!$(event.srcElement).closest('.note-editable, .note-popover, .note-link-dialog, .note-image-dialog, .note-air-dialog').length) {
            $(".note-popover > *:not(#note-undo-popover)").hide();
        }
    }
    var fn_attach = eventHandler.attach;
    eventHandler.attach = function (oLayoutInfo, options) {
        fn_attach.call(this, oLayoutInfo, options);
        oLayoutInfo.editor.on('dragstart', 'img', function (e) { e.preventDefault(); });
        $(document).on('mousedown', summernote_mousedown);
        $(document).on('mouseup', summernote_mouseup);
        $(document).on('click', summernote_click);
        oLayoutInfo.editor.off('click').on('click', function (e) {e.preventDefault();}); // if the content editable is a link
        oLayoutInfo.editor.on('dblclick', 'img, .media_iframe_video, span.fa, i.fa, span.fa', function (event) {
            new website.editor.MediaDialog(oLayoutInfo.editor, event.target).appendTo(document.body);
        });
        
        var clone_data = false;
        var $node = oLayoutInfo.editor;
        if ($node.data('oe-model')) {
            var $nodes = $('[data-oe-model]')
                .filter(function () { return this != $node[0];})
                .filter('[data-oe-model="'+$node.data('oe-model')+'"]')
                .filter('[data-oe-id="'+$node.data('oe-id')+'"]')
                .filter('[data-oe-field="'+$node.data('oe-field')+'"]');
            if ($node.data('oe-type')) $nodes = $nodes.filter('[data-oe-type="'+$node.data('oe-type')+'"]');
            if ($node.data('oe-expression')) $nodes = $nodes.filter('[data-oe-expression="'+$node.data('oe-expression')+'"]');
            if ($node.data('oe-xpath')) $nodes = $nodes.filter('[data-oe-xpath="'+$node.data('oe-xpath')+'"]');

            if ($nodes.length) {
                $node.on('content_changed', function () {
                    if (!clone_data) {
                        clone_data = true;
                        $nodes.html(this.innerHTML);
                        clone_data = false;
                    }
                });
            }
        }
    };
    var fn_dettach = eventHandler.dettach;
    eventHandler.dettach = function (oLayoutInfo, options) {
        fn_dettach.call(this, oLayoutInfo, options);
        oLayoutInfo.editor.off("dragstart");
        $(document).off('mousedown', summernote_mousedown);
        $(document).off('mouseup', summernote_mouseup);
        $(document).off('click', summernote_click);
        oLayoutInfo.editor.off("dblclick");
    };

    //////////////////////////////////////////////////////////////////////////////////////////////////////////
    /* Change History to have a global History for all summernote instances */

    var History = function History () {
        var aUndo = [];
        var pos = 0;

        this.makeSnap = function ($editable) {
            var elEditable = $editable[0],
                rng = range.create();
            return {
                editable: elEditable,
                contents: $editable.html(),
                bookmark: rng.bookmark(elEditable),
                scrollTop: $editable.scrollTop()
            };
        };

        this.applySnap = function (oSnap) {
            var $editable = $(oSnap.editable);
            $editable.trigger('mousedown');

            $editable.html(oSnap.contents).scrollTop(oSnap.scrollTop);
            var r = range.createFromBookmark(oSnap.editable, oSnap.bookmark);
            r.select();

            $(document).trigger("click");
            $(".oe_overlay").remove();
            $(".o_editable *").filter(function () {
                var $el = $(this);
                if($el.data('snippet-editor')) {
                    $el.removeData();
                }
            });

            setTimeout(function () {
                var target = r.sc.tagName ? r.sc : r.sc.parentNode;
                var evt = document.createEvent("MouseEvents");
                evt.initMouseEvent("click", true, true, window, 0, 0, 0, 0, 0, false, false, false, false, 0, target);
                target.dispatchEvent(evt);
            },0);
        };

        this.undo = function ($editable) {
            if (!pos) { return; }
            last = null;
            if (!aUndo[pos]) aUndo[pos] = this.makeSnap($editable || $('.o_editable.note-editable:first'));
            if (aUndo[pos-1].jump) pos--;
            this.applySnap(aUndo[--pos]);
        };
        this.hasUndo = function ($editable) {
            return pos > 0;
        };

        this.redo = function () {
            if (aUndo.length <= pos+1) { return; }
            if (aUndo[pos].jump) pos++;
            this.applySnap(aUndo[++pos]);
        };
        this.hasRedo = function () {
            return aUndo.length > pos+1;
        };

        this.popUndo = function () {
            aUndo.pop();
        };

        var last;
        this.recordUndo = function ($editable, event) {
            if (event) {
                if (last && aUndo[pos-1] && aUndo[pos-1].editable !== $editable[0]) {
                    // => make a snap when the user change editable zone (because: don't make snap for each keydown)
                    aUndo.splice(pos, aUndo.length);
                    var prev = aUndo[pos-1];
                    aUndo[pos] = {
                        editable: prev.editable,
                        contents: $(prev.editable).html(),
                        bookmark: prev.bookmark,
                        scrollTop: prev.scrollTop,
                        jump: true
                    };
                    pos++;
                }
                else if (event === last) return;
            }
            last = event;
            aUndo.splice(pos, aUndo.length);
            aUndo[pos] = this.makeSnap($editable);
            pos++;
        };

        this.splitNext = function () {
            last = false;
        };
    };
    var history = new History();

    //////////////////////////////////////////////////////////////////////////////////////////////////////////
    // add focusIn to jQuery to allow to move caret into a div of a contentEditable area

    $.fn.extend({
        focusIn: function () {
            if (this.length) {
                var node = dom.firstChild(this[0]);
                range.create(node, 0, node, 0).select();
            }
            return this;
        }
    });

    //////////////////////////////////////////////////////////////////////////////////////////////////////////

    website.no_editor = !!$(document.documentElement).data('editable-no-editor');

    website.add_template_file('/website/static/src/xml/website.editor.xml');
    website.dom_ready.done(function () {
        var is_smartphone = $(document.body)[0].clientWidth < 767;

        if (!is_smartphone) {
            website.ready().then(website.init_editor);
        } else {
            var resize_smartphone = function () {
                is_smartphone = $(document.body)[0].clientWidth < 767;
                if (!is_smartphone) {
                    $(window).off("resize", resize_smartphone);
                    website.init_editor();
                }
            };
            $(window).on("resize", resize_smartphone);
        }

        $(document).on('click', 'a.js_link2post', function (ev) {
            ev.preventDefault();
            website.form(this.pathname, 'POST');
        });

        $(document).on('click', '.note-editable', function (ev) {
            ev.preventDefault();
        });

        $(document).on('submit', '.note-editable form .btn', function (ev) {
            // Disable form submition in editable mode
            ev.preventDefault();
        });

        $(document).on('hide.bs.dropdown', '.dropdown', function (ev) {
            // Prevent dropdown closing when a contenteditable children is focused
            if (ev.originalEvent
                    && $(ev.target).has(ev.originalEvent.target).length
                    && $(ev.originalEvent.target).is('[contenteditable]')) {
                ev.preventDefault();
            }
        });
    });

    website.init_editor = function () {
        var editor = new website.EditorBar();
        var $body = $(document.body);
        editor.prependTo($body).then(function () {
            if (location.search.indexOf("enable_editor") >= 0) {
                editor.edit();
            }
        });
        website.editor_bar = editor;
    };
    
    /* ----- TOP EDITOR BAR FOR ADMIN ---- */
    website.EditorBar = openerp.Widget.extend({
        template: 'website.editorbar',
        events: {
            'click button[data-action=save]': 'save',
            'click a[data-action=cancel]': 'cancel',
        },
        start: function() {
            var self = this;
            this.saving_mutex = new openerp.Mutex();

            this.$buttons = {
                edit: this.$el.parents().find('button[data-action=edit]'),
                save: this.$('button[data-action=save]'),
                cancel: this.$('button[data-action=cancel]'),
            };

            this.$('#website-top-edit').hide();
            this.$('#website-top-view').show();

            var $edit_button = this.$buttons.edit
                    .prop('disabled', website.no_editor);
            if (website.no_editor) {
                var help_text = $(document.documentElement).data('editable-no-editor');
                $edit_button.parent()
                    // help must be set on form above button because it does
                    // not appear on disabled button
                    .attr('title', help_text);
            }

            $('.dropdown-toggle').dropdown();

            this.$buttons.edit.click(function(ev) {
                self.edit();
            });

            this.rte = new website.RTE(this);
            this.rte.on('change', this, this.proxy('rte_changed'));
            this.rte.on('rte:ready', this, function () {
                self.trigger('rte:ready');
            });

            this.rte.appendTo(this.$('#website-top-edit .nav.js_editor_placeholder'));
            return this._super.apply(this, arguments);
        },
        edit: function () {
            this.$buttons.edit.prop('disabled', true);
            this.$('#website-top-view').hide();
            this.$el.show();
            this.$('#website-top-edit').show();
            $('.css_non_editable_mode_hidden').removeClass("css_non_editable_mode_hidden");
            
            this.rte.start_edition();
            this.trigger('rte:called');

            window.onbeforeunload = function(event) {
                if ($('.o_editable.o_dirty').length) {
                    return _t('This document is not saved!');
                }
            };
        },
        rte_changed: function () {
            this.$buttons.save.prop('disabled', false);
        },
        save: function () {
            var self = this;

            var saved = {}; // list of allready saved views and data

            observer.disconnect();
            var defs = $('.o_editable')
                .filter('.o_dirty')
                .removeAttr('contentEditable')
                .removeClass('o_dirty o_editable cke_focus oe_carlos_danger')
                .map(function () {
                    var $el = $(this);

                    // remove multi edition
                    var key =  $el.data('oe-model')+":"+$el.data('oe-id')+":"+$el.data('oe-field')+":"+$el.data('oe-type')+":"+$el.data('oe-expression');
                    if (saved[key]) return true;
                    saved[key] = true;

                    // TODO: Add a queue with concurrency limit in webclient
                    // https://github.com/medikoo/deferred/blob/master/lib/ext/function/gate.js
                    return self.saving_mutex.exec(function () {
                        return self.saveElement($el)
                            .then(undefined, function (thing, response) {
                                // because ckeditor regenerates all the dom,
                                // we can't just setup the popover here as
                                // everything will be destroyed by the DOM
                                // regeneration. Add markings instead, and
                                // returns a new rejection with all relevant
                                // info
                                var id = _.uniqueId('carlos_danger_');
                                $el.addClass('o_dirty oe_carlos_danger');
                                $el.addClass(id);
                                return $.Deferred().reject({
                                    id: id,
                                    error: response.data,
                                });
                            });
                    });
                }).get();
            return $.when.apply(null, defs).then(function () {
                window.onbeforeunload = null;
                website.reload();
            }, function (failed) {
                // If there were errors, re-enable edition
                self.rte.start_edition(true);
                // jquery's deferred being a pain in the ass
                if (!_.isArray(failed)) { failed = [failed]; }

                _(failed).each(function (failure) {
                    var html = failure.error.exception_type === "except_osv";
                    if (html) {
                        var msg = $("<div/>").text(failure.error.message).html();
                        var data = msg.substring(3,msg.length-2).split(/', u'/);
                        failure.error.message = '<b>' + data[0] + '</b>' + dom.blank + data[1];
                    }
                    $(root).find('.' + failure.id)
                        .removeClass(failure.id)
                        .popover({
                            html: html,
                            trigger: 'hover',
                            content: failure.error.message,
                            placement: 'auto top',
                        })
                        // Force-show popovers so users will notice them.
                        .popover('show');
                });
            });
        },
        /**
         * Saves an RTE content, which always corresponds to a view section (?).
         */
        saveElement: function ($el) {
            var markup = $el.prop('outerHTML');
            return openerp.jsonRpc('/web/dataset/call', 'call', {
                model: 'ir.ui.view',
                method: 'save',
                args: [$el.data('oe-id'), markup,
                       $el.data('oe-xpath') || null,
                       website.get_context()],
            });
        },
        cancel: function () {
            new $.Deferred(function (d) {
                var $dialog = $(openerp.qweb.render('website.editor.discard')).appendTo(document.body);
                $dialog.on('click', '.btn-danger', function () {
                    d.resolve();
                }).on('hidden.bs.modal', function () {
                    d.reject();
                });
                d.always(function () {
                    $dialog.remove();
                });
                $dialog.modal('show');
            }).then(function () {
                window.onbeforeunload = null;
                website.reload();
            });
        },
    });
    
    website.EditorBarCustomize = openerp.Widget.extend({
        events: {
            'mousedown a.dropdown-toggle': 'load_menu',
            'click ul a[data-view-id]': 'do_customize',
        },
        start: function() {
            var self = this;
            this.$menu = self.$el.find('ul');
            this.view_name = $(document.documentElement).data('view-xmlid');
            if (!this.view_name) {
                this.$el.hide();
            }
            this.loaded = false;
        },
        load_menu: function () {
            var self = this;
            if(this.loaded) {
                return;
            }
            openerp.jsonRpc('/website/customize_template_get', 'call', { 'xml_id': this.view_name }).then(
                function(result) {
                    _.each(result, function (item) {
                        if (item.xml_id === "website.debugger" && !window.location.search.match(/[&?]debug(&|$)/)) return;
                        if (item.header) {
                            self.$menu.append('<li class="dropdown-header">' + item.name + '</li>');
                        } else {
                            self.$menu.append(_.str.sprintf('<li role="presentation"><a href="#" data-view-id="%s" role="menuitem"><strong class="fa fa%s-square-o"></strong> %s</a></li>',
                                item.id, item.active ? '-check' : '', item.name));
                        }
                    });
                    self.loaded = true;
                }
            );
        },
        do_customize: function (event) {
            var view_id = $(event.currentTarget).data('view-id');
            return openerp.jsonRpc('/web/dataset/call_kw', 'call', {
                model: 'ir.ui.view',
                method: 'toggle',
                args: [],
                kwargs: {
                    ids: [parseInt(view_id, 10)],
                    context: website.get_context()
                }
            }).then( function() {
                window.location.reload();
            });
        },
    });

    $(document).ready(function() {
        var editorBarCustomize = new website.EditorBarCustomize();
        editorBarCustomize.setElement($('li[id=customize-menu]'));
        editorBarCustomize.start();
    });

    /* ----- RICH TEXT EDITOR ---- */

    website.RTE = openerp.Widget.extend({
        init: function (EditorBar) {
            this.EditorBar = EditorBar;
            $('.inline-media-link').remove();
            this._super.apply(this, arguments);
        },
        /**
         * Add a record undo to history
         * @param {DOM} target where the dom is changed is editable zone
         */
        historyRecordUndo: function ($target) {
            var $editable = $target.is('[data-oe-model], .o_editable') ? $target : $target.closest('[data-oe-model], .o_editable');
            $target.mousedown();
            if (!range.create()) {
                range.create($target[0],0,$target[0],0).select();
            }
            this.history.recordUndo( $editable );
            $target.mousedown();
        },
        /**
         * Makes the page editable
         *
         * @param {Boolean} [restart=false] in case the edition was already set
         *                                  up once and is being re-enabled.
         * @returns {$.Deferred} deferred indicating when the RTE is ready
         */
        start_edition: function (restart) {
            var self = this;

            this.history = history;

            // handler for cancel editor
            $(document).on('keydown', function (event) {
                if (event.keyCode === 27 && !$('.modal-content:visible').length) {
                    setTimeout(function () {
                        $('#website-top-navbar [data-action="cancel"]').click();
                        var $modal = $('.modal-content > .modal-body').parents(".modal:first");
                        $modal.off('keyup.dismiss.bs.modal');
                        setTimeout(function () {
                            $modal.on('keyup.dismiss.bs.modal', function () {
                                $(this).modal('hide');
                            });
                        },500);
                    },0);
                }
            });

            // activate editor
            var $last;
            $(document).on('mousedown', function (event) {
                var $target = $(event.target);
                var $editable = $target.closest('.o_editable');

                if (!$editable.size()) {
                    return;
                }

                if ($last && (!$editable.size() || $last[0] != $editable[0])) {
                    $last.destroy();
                    $last = null;
                }
                if ($editable.size() && (!$last || $last[0] != $editable[0])) {
                    $editable.summernote(self._config());
                    $editable.data('NoteHistory', self.history);
                    $editable.data('rte', self);
                    $last = $editable;

                    try {
                        document.execCommand('enableObjectResizing', false, false);
                        document.execCommand('enableInlineTableEditing', false, false);
                        document.execCommand( '2D-position', false, false);
                    } catch (e) {}

                    document.body.addEventListener('mscontrolselect', function (evt) {evt.preventDefault(); return false;});
                    document.body.addEventListener('controlselect', function (evt) {evt.preventDefault(); return false;});
                    document.body.addEventListener('resizestart', function (evt) {evt.preventDefault(); return false;});
                    document.body.addEventListener('movestart', function (evt) {evt.preventDefault(); return false;});
                    document.body.addEventListener('dragstart', function (evt) {evt.preventDefault(); return false;});

                    if (!range.create()) {
                        range.create(dom.firstChild($editable[0]),0).select();
                    }
                }
            });

            $('#wrapwrap [data-oe-model]')
                .not('link, script')
                .not('img[data-oe-field="arch"], br[data-oe-field="arch"], input[data-oe-field="arch"]')
                .not('.oe_snippet_editor')
                .addClass('o_editable');

            $('.o_editable').each(function () {
                var node = this;
                var $node = $(node);
                // start element observation
                observer.observe(node, OBSERVER_CONFIG);
                $(node).one('content_changed', function () {
                    $node.addClass('o_dirty');
                    self.trigger('change');
                });
            });

            if (!restart) {
                $('#wrapwrap, .o_editable').on('click', '*', function (event) {
                    event.preventDefault();
                });
                self.trigger('rte:ready');
            }
        },

        _config: function () {
            return {
                airMode : true,
                focus: false,
                airPopover: [
                    ['style', ['style']],
                    ['font', ['bold', 'italic', 'underline', 'clear']],
                    ['fontsize', ['fontsize']],
                    ['color', ['color']],
                    ['para', ['ul', 'ol', 'paragraph']],
                    ['table', ['table']],
                    ['insert', ['link', 'picture']],
                    ['history', ['undo', 'redo']],
                ],
                oninit: function() {
                },
                styleWithSpan: false,
                inlinemedia : ['p']
            };
        }
    });

    /* ----- OBSERVER ---- */

    website.Observer = window.MutationObserver || window.WebKitMutationObserver || window.JsMutationObserver;
    var OBSERVER_CONFIG = {
        childList: true,
        attributes: true,
        characterData: true,
        subtree: true,
        attributeOldValue: true,
    };
    var observer = new website.Observer(function (mutations) {
        // NOTE: Webkit does not fire DOMAttrModified => webkit browsers
        //       relying on JsMutationObserver shim (Chrome < 18, Safari < 6)
        //       will not mark dirty on attribute changes (@class, img/@src,
        //       a/@href, ...)
        _(mutations).chain()
            .filter(function (m) {
                // ignore any SVG target, these blokes are like weird mon
                if (m.target && m.target instanceof SVGElement) {
                    return false;
                }
                // ignore any change related to mundane image-edit-button
                if (m.target && m.target.className
                        && m.target.className.indexOf('image-edit-button') !== -1) {
                    return false;
                }
                switch(m.type) {
                    case 'attributes':
                        // ignore contenteditable modification
                        if (m.attributeName === 'contenteditable') { return false; }
                        if (m.attributeName === 'attributeeditable') { return false; }
                        // remove content editable attribute from firefox
                        if (m.attributeName.indexOf('_moz') === 0) {
                            if (!m.oldValue) {
                                // remove stupid _moz attributes
                                $(m.target).filter(function () { return this.attributes[m.attributeName]; }).removeAttr(m.attributeName);
                            }
                            return false;
                        }
                        // ignore id modification
                        if (m.attributeName === 'id') { return false; }
                        // style not change
                        if (m.attributeName === 'style' && (m.oldValue || "") === (m.target.attributes.style ? m.target.attributes.style.value : "")) { return false; }
                        // if attribute is not a class, can't be .cke_focus change
                        if (m.attributeName !== 'class') { return true; }

                        // find out what classes were added or removed
                        var oldClasses = (m.oldValue || '').split(/\s+/);
                        var newClasses = m.target.className.split(/\s+/);
                        var change = _.union(_.difference(oldClasses, newClasses),
                                             _.difference(newClasses, oldClasses));
                        // ignore mutation to create editable zone and add dirty class
                        var change = _.difference(change, ["note-air-editor", "note-editable", "o_dirty", "o_editable", ""]);
                        return !!change.length;
                    case 'childList':
                        // Remove ignorable nodes from addedNodes or removedNodes,
                        // if either set remains non-empty it's considered to be an
                        // impactful change. Otherwise it's ignored.
                        return !!remove_mundane_nodes(m.addedNodes).length ||
                               !!remove_mundane_nodes(m.removedNodes).length;
                    default:
                        return true;
                }
            })
            .map(function (m) {
                var node = m.target;
                while (node && (!node.className || node.className.indexOf('o_editable')===-1)) {
                    node = node.parentNode;
                }
                if (node) {
                    $(node).data('last-mutation', m);
                }
                return node;
            })
            .compact()
            .uniq()
            .each(function (node) {
                $(node).trigger('content_changed');
            });
    });
    function remove_mundane_nodes(nodes) {
        if (!nodes || !nodes.length) { return []; }

        var output = [];
        for(var i=0; i<nodes.length; ++i) {
            var node = nodes[i];
            if (node.nodeType === document.ELEMENT_NODE) {
                if (node.nodeName === 'BR' && node.getAttribute('type') === '_moz') {
                    // <br type="_moz"> appears when focusing RTE in FF, ignore
                    continue;
                } else if (node.nodeName === 'DIV' && $(node).hasClass('oe_drop_zone')) {
                    // ignore dropzone inserted by snippets
                    continue
                }
            }

            output.push(node);
        }
        return output;
    }

    /* ----- EDITOR: LINK & MEDIA ---- */

    website.editor = { };
    website.editor.Dialog = openerp.Widget.extend({
        events: {
            'hidden.bs.modal': 'destroy',
            'click button.save': 'save',
            'click button[data-dismiss="modal"]': 'cancel',
        },
        init: function () {
            this._super();
        },
        start: function () {
            var sup = this._super();
            this.$el.modal({backdrop: 'static'});
            this.$('input:first').focus();
            return sup;
        },
        save: function () {
            this.close();
            this.trigger("saved");
        },
        cancel: function () {
            this.trigger("cancel");
        },
        close: function () {
            this.$el.modal('hide');
        },
    });

    website.editor.LinkDialog = website.editor.Dialog.extend({
        template: 'website.editor.dialog.link',
        events: _.extend({}, website.editor.Dialog.prototype.events, {
            'change :input.url-source': 'changed',
            'keyup :input.url': 'onkeyup',
            'keyup :input': 'preview',
            'click button.remove': 'remove_link',
            'change input#link-text': function (e) {
                this.text = $(e.target).val();
            },
            'change .link-style': function (e) {
                this.preview();
            },
        }),
        init: function (editable, data) {
            this._super(editable, data);
            this.editable = editable;
            this.data = data;

            this.data.text = this.data.text.replace(/[ \t\r\n]+/g, ' ');
            this.data.className = "";
            if (this.data.range) {
                this.data.iniClassName = $(this.data.range.sc).attr("class") || "";
                this.data.className = this.data.iniClassName.replace(/(^|\s+)(btn(?!\s|$)|btn-[a-z0-9_-]*)/gi, '');
            }

            // Store last-performed request to be able to cancel/abort it.
            this.page_exists_req = null;
            this.search_pages_req = null;
            this.bind_data();
        },
        start: function () {
            var self = this;
            var last;
            this.$('#link-page').select2({
                minimumInputLength: 1,
                placeholder: _t("New or existing page"),
                query: function (q) {
                    if (q.term == last) return;
                    last = q.term;
                    $.when(
                        self.page_exists(q.term),
                        self.fetch_pages(q.term)
                    ).then(function (exists, results) {
                        var rs = _.map(results, function (r) {
                            return { id: r.loc, text: r.loc, };
                        });
                        if (!exists) {
                            rs.push({
                                create: true,
                                id: q.term,
                                text: _.str.sprintf(_t("Create page '%s'"), q.term),
                            });
                        }
                        q.callback({
                            more: false,
                            results: rs
                        });
                    }, function () {
                        q.callback({more: false, results: []});
                    });
                },
            });
            return this._super().then(this.proxy('bind_data'));
        },
        get_data: function (test) {
            var self = this,
                def = new $.Deferred(),
                $e = this.$('.active input.url-source').filter(':input'),
                val = $e.val(),
                label = this.$('#link-text').val() || val;

            if (!test && (!val || !$e[0].checkValidity())) {
                // FIXME: error message
                $e.closest('.form-group').addClass('has-error');
                $e.focus();
                def.reject();
            }

            var style = this.$("input[name='link-style-type']:checked").val() || '';
            var size = this.$("input[name='link-style-size']:checked").val() || '';
            var classes = (this.data.className || "") + (style && style.length ? " btn " : "") + style + " " + size;

            var done = $.when();
            if ($e.hasClass('email-address') && $e.val().indexOf("@") !== -1) {
                def.resolve('mailto:' + val, false, label, classes);
            } else if ($e.val() && $e.val().length && $e.hasClass('page')) {
                var data = $e.select2('data');
                if (test || !data.create) {
                    def.resolve(data.id, false, label || data.text, classes);
                } else {
                    // Create the page, get the URL back
                    $.get(_.str.sprintf(
                            '/website/add/%s?noredirect=1', encodeURI(data.id)))
                        .then(function (response) {
                            def.resolve(response, false, label, classes);
                        });
                }
            } else {
                def.resolve(val, this.$('input.window-new').prop('checked'), label, classes);
            }
            return def;
        },
        save: function () {
            var self = this;
            var _super = this._super.bind(this);
            return this.get_data()
                .then(function (url, new_window, label, classes) {
                    self.data.url = url;
                    self.data.newWindow = new_window;
                    self.data.text = label;
                    self.data.className = classes;

                    self.trigger("save", self.data);
                }).then(_super);
        },
        bind_data: function () {
            var href = this.data.url;
            var new_window = this.data.newWindow;
            var text = this.data.text;
            var classes = this.data.iniClassName;

            this.$('input#link-text').val(text);
            this.$('input.window-new').prop('checked', new_window);

            if (classes) {
                this.$('input[value!=""]').each(function () {
                    var $option = $(this);
                    if (classes.indexOf($option.val()) !== -1) {
                        $option.attr("checked", "checked");
                    }
                });
            }

            var match, $control;
            if (href && (match = /mailto:(.+)/.exec(href))) {
                this.$('input.email-address').val(match[1]).change();
            }
            if (href && !$control) {
                this.page_exists(href).then(function (exist) {
                    if (exist) {
                        self.$('#link-page').select2('data', {'id': href, 'text': href});
                    } else {
                        self.$('input.url').val(href).change();
                        self.$('input.window-new').closest("div").show();
                    }
                });
            }

            this.page_exists(href).then(function (exist) {
                if (exist) {
                    self.$('#link-page').select2('data', {'id': href, 'text': href});
                } else {
                    self.$('input.url').val(href).change();
                    self.$('input.window-new').closest("div").show();
                }
            });

            this.preview();
        },
        changed: function (e) {
            var $e = $(e.target);
            this.$('.url-source').filter(':input').not($e).val('')
                    .filter(function () { return !!$(this).data('select2'); })
                    .select2('data', null);
            $e.closest('.list-group-item')
                .addClass('active')
                .siblings().removeClass('active')
                .addBack().removeClass('has-error');
            this.preview();
        },
        call: function (method, args, kwargs) {
            var self = this;
            var req = method + '_req';
            if (this[req]) { this[req].abort(); }
            return this[req] = openerp.jsonRpc('/web/dataset/call_kw', 'call', {
                model: 'website',
                method: method,
                args: args,
                kwargs: kwargs,
            }).always(function () {
                self[req] = null;
            });
        },
        page_exists: function (term) {
            return this.call('page_exists', [null, term], {
                context: website.get_context(),
            });
        },
        fetch_pages: function (term) {
            return this.call('search_pages', [null, term], {
                limit: 9,
                context: website.get_context(),
            });
        },
        onkeyup: function (e) {
            var $e = $(e.target);
            var is_link = ($e.val()||'').length && $e.val().indexOf("@") === -1;
            this.$('input.window-new').closest("div").toggle(is_link);
            this.preview();
        },
        preview: function () {
            var $preview = this.$("#link-preview");
            this.get_data(true).then(function (url, new_window, label, classes) {
                $preview.attr("target", new_window ? '_blank' : "")
                    .text((label && label.length ? label : url))
                    .attr("class", classes.replace(/pull-\w+/, ''));
            });
        }
    });

    website.editor.Media = openerp.Widget.extend({
        init: function (parent, media) {
            this._super();
            this.parent = parent;
            this.media = media;
        },
        start: function () {
            this.$preview = this.$('.preview-container').detach();
            return this._super();
        },
        search: function (needle) {
        },
        save: function () {
        },
        clear: function () {
        },
        cancel: function () {
        },
        close: function () {
        },
    });

    website.editor.MediaDialog = website.editor.Dialog.extend({
        template: 'website.editor.dialog.media',
        events : _.extend({}, website.editor.Dialog.prototype.events, {
            'input input#icon-search': 'search',
        }),
        init: function ($editable, media) {
            this._super();
            if ($editable) {
                this.$editable = $editable;
                this.rte = this.$editable.rte || this.$editable.data('rte');
            }
            this.media = media;
        },
        start: function () {
            var self = this;

            this.range = range.create();

            if (this.media) {
                if (this.media.nodeName === "IMG") {
                    this.$('[href="#editor-media-image"]').tab('show');
                } else if (this.media.className.match(/(^|\s)media_iframe_video($|\s)/)) {
                    this.$('[href="#editor-media-video"]').tab('show');
                }  else if (this.media.parentNode.className.match(/(^|\s)media_iframe_video($|\s)/)) {
                    this.media = this.media.parentNode;
                    this.$('[href="#editor-media-video"]').tab('show');
                } else if (this.media.className.match(/(^|\s)fa($|\s)/)) {
                    this.$('[href="#editor-media-icon"]').tab('show');
                }

                if ($(this.media).parent().data("oe-field") === "image") {
                    this.$('[href="#editor-media-video"], [href="#editor-media-icon"]').addClass('hidden');
                }
            }

            this.imageDialog = new website.editor.RTEImageDialog(this, this.media);
            this.imageDialog.appendTo(this.$("#editor-media-image"));
            this.iconDialog = new website.editor.FontIconsDialog(this, this.media);
            this.iconDialog.appendTo(this.$("#editor-media-icon"));
            this.videoDialog = new website.editor.VideoDialog(this, this.media);
            this.videoDialog.appendTo(this.$("#editor-media-video"));

            this.active = this.imageDialog;

            $('a[data-toggle="tab"]').on('shown.bs.tab', function (event) {
                if ($(event.target).is('[href="#editor-media-image"]')) {
                    self.active = self.imageDialog;
                    self.$('li.search, li.previous, li.next').removeClass("hidden");
                } else if ($(event.target).is('[href="#editor-media-icon"]')) {
                    self.active = self.iconDialog;
                    self.$('li.search, li.previous, li.next').removeClass("hidden");
                    self.$('.nav-tabs li.previous, .nav-tabs li.next').addClass("hidden");
                } else if ($(event.target).is('[href="#editor-media-video"]')) {
                    self.active = self.videoDialog;
                    self.$('.nav-tabs li.search').addClass("hidden");
                }
            });

            return this._super();
        },
        save: function () {
            if(this.rte) this.rte.historyRecordUndo(this.$editable);
            this.trigger("save");

            var self = this;
            if (self.media) {
                this.media.innerHTML = "";
                if (this.active !== this.imageDialog) {
                    this.imageDialog.clear();
                }
                if (this.active !== this.iconDialog) {
                    this.iconDialog.clear();
                }
                if (this.active !== this.videoDialog) {
                    this.videoDialog.clear();
                }
            } else {
                this.media = document.createElement("img");
                this.range.insertNode(this.media);
                this.active.media = this.media;
                this.media.className = "img-responsive pull-left";
            }
            var $el = $(self.active.media);
            this.active.save();
            //this.media.className = this.media.className.replace(/\s+/g, ' ');
            setTimeout(function () {
                $el.trigger("saved", self.active.media);
                $(document.body).trigger("media-saved", [$el[0], self.active.media]);
                range.create(self.active.media, 0, self.active.media.nextSibling || self.active.media, 0).select();
                $(self.active.media).trigger("mouseup");
            },0);
            this._super();
        },
        searchTimer: null,
        search: function () {
            var self = this;
            var needle = this.$("input#icon-search").val();
            clearTimeout(this.searchTimer);
            this.searchTimer = setTimeout(function () {
                self.active.search(needle || "");
            },250);
        }
    });

    /**
     * ImageDialog widget. Lets users change an image, including uploading a
     * new image in OpenERP or selecting the image style (if supported by
     * the caller).
     *
     * Initialized as usual, but the caller can hook into two events:
     *
     * @event start({url, style}) called during dialog initialization and
     *                            opening, the handler can *set* the ``url``
     *                            and ``style`` properties on its parameter
     *                            to provide these as default values to the
     *                            dialog
     * @event save({url, style}) called during dialog finalization, the handler
     *                           is provided with the image url and style
     *                           selected by the users (or possibly the ones
     *                           originally passed in)
     */
    var IMAGES_PER_ROW = 6;
    var IMAGES_ROWS = 2;
    website.editor.ImageDialog = website.editor.Media.extend({
        template: 'website.editor.dialog.image',
        events: _.extend({}, website.editor.Dialog.prototype.events, {
            'change .url-source': function (e) {
                this.changed($(e.target));
            },
            'click button.filepicker': function () {
                var filepicker = this.$('input[type=file]');
                if (!_.isEmpty(filepicker)){
                    filepicker[0].click();
                }
            },
            'click .js_disable_optimization': function () {
                this.$('input[name="disable_optimization"]').val('1');
                var filepicker = this.$('button.filepicker');
                if (!_.isEmpty(filepicker)){
                    filepicker[0].click();
                }
            },
            'change input[type=file]': 'file_selection',
            'submit form': 'form_submit',
            'change input.url': "change_input",
            'keyup input.url': "change_input",
            //'change select.image-style': 'preview_image',
            'click .existing-attachments img': 'select_existing',
            'click .existing-attachment-remove': 'try_remove',
        }),
        init: function (parent, media) {
            this.page = 0;
            this._super(parent, media);
        },
        start: function () {
            var self = this;
            var res = this._super();
            var o = { url: null };
            // avoid typos, prevent addition of new properties to the object
            Object.preventExtensions(o);
            this.trigger('start', o);
            this.parent.$(".pager > li").click(function (e) {
                e.preventDefault();
                var $target = $(e.currentTarget);
                if ($target.hasClass('disabled')) {
                    return;
                }
                self.page += $target.hasClass('previous') ? -1 : 1;
                self.display_attachments();
            });
            this.set_image(o.url);
            return res;
        },
        save: function () {
            if (!this.link) {
                this.link = this.$(".existing-attachments img:first").attr('src');
            }

            if (this.media.tagName !== "IMG") {
                var media = document.createElement('img');
                $(this.media).replaceWith(media);
                this.media = media;
            }

            this.trigger('save', {
                url: this.link
            });

            $(this.media).attr('src', this.link);
            return this._super();
        },
        clear: function () {
            this.media.className = this.media.className.replace(/(^|\s)(img(\s|$)|img-[^\s]*)/g, ' ');
        },
        cancel: function () {
            this.trigger('cancel');
        },
        change_input: function (e) {
            var $input = $(e.target);
            var $button = $input.parent().find("button");
            if ($input.val() === "") {
                $button.addClass("btn-default").removeClass("btn-primary");
            } else {
                $button.removeClass("btn-default").addClass("btn-primary");
            }
        },
        search: function (needle) {
            var self = this;
            this.fetch_existing(needle).then(function () {
                self.selected_existing(self.$('input.url').val());
            });
        },
        set_image: function (url, error) {
            var self = this;
            if (url) this.link = url;
            this.$('input.url').val('');
            this.fetch_existing().then(function () {
                self.selected_existing(url);
            });
        },
        form_submit: function (event) {
            var self = this;
            var $form = this.$('form[action="/website/attach"]');
            if (!$form.find('input[name="upload"]').val().length) {
                var url = $form.find('input[name="url"]').val();
                if (this.selected_existing(url).size()) {
                    event.preventDefault();
                    return false;
                }
            }
            var callback = _.uniqueId('func_');
            this.$('input[name=func]').val(callback);
            window[callback] = function (attachments, error) {
                delete window[callback];
                self.file_selected(attachments[0]['website_url'], error);
            };
        },
        file_selection: function () {
            this.$el.addClass('nosave');
            this.$('form').removeClass('has-error').find('.help-block').empty();
            this.$('button.filepicker').removeClass('btn-danger btn-success');
            this.$('form').submit();
        },
        file_selected: function(url, error) {
            var $button = this.$('button.filepicker');
            if (!error) {
                $button.addClass('btn-success');
            } else {
                url = null;
                this.$('form').addClass('has-error')
                    .find('.help-block').text(error);
                $button.addClass('btn-danger');
            }
            this.set_image(url, error);
            // auto save and close popup
            this.parent.save();
        },
        fetch_existing: function (needle) {
            var domain = [['res_model', '=', 'ir.ui.view'], '|',
                        ['mimetype', '=', false], ['mimetype', '=like', 'image/%']];
            if (needle && needle.length) {
                domain.push('|', ['datas_fname', 'ilike', needle], ['name', 'ilike', needle]);
            }
            return openerp.jsonRpc('/web/dataset/call_kw', 'call', {
                model: 'ir.attachment',
                method: 'search_read',
                args: [],
                kwargs: {
                    fields: ['name', 'website_url'],
                    domain: domain,
                    order: 'id desc',
                    context: website.get_context(),
                }
            }).then(this.proxy('fetched_existing'));
        },
        fetched_existing: function (records) {
            this.records = records;
            this.display_attachments();
        },
        display_attachments: function () {
            this.$('.help-block').empty();
            var per_screen = IMAGES_PER_ROW * IMAGES_ROWS;

            var from = this.page * per_screen;
            var records = this.records;

            // Create rows of 3 records
            var rows = _(records).chain()
                .slice(from, from + per_screen)
                .groupBy(function (_, index) { return Math.floor(index / IMAGES_PER_ROW); })
                .values()
                .value();
            this.$('.existing-attachments').replaceWith(
                openerp.qweb.render(
                    'website.editor.dialog.image.existing.content', {rows: rows}));
            this.parent.$('.pager')
                .find('li.previous').toggleClass('disabled', (from === 0)).end()
                .find('li.next').toggleClass('disabled', (from + per_screen >= records.length));
        },
        select_existing: function (e) {
            var link = $(e.currentTarget).attr('src');
            this.link = link;
            this.selected_existing(link);
        },
        selected_existing: function (link) {
            this.$('.existing-attachment-cell.media_selected').removeClass("media_selected");
            var $select = this.$('.existing-attachment-cell img').filter(function () {
                return $(this).attr("src") == link;
            }).first();
            $select.parent().addClass("media_selected");
            return $select;
        },
        try_remove: function (e) {
            var $help_block = this.$('.help-block').empty();
            var self = this;
            var $a = $(e.target);
            var id = parseInt($a.data('id'), 10);
            var attachment = _.findWhere(this.records, {id: id});
            var $both = $a.parent().children();

            $both.css({borderWidth: "5px", borderColor: "#f00"});

            return openerp.jsonRpc('/web/dataset/call_kw', 'call', {
                model: 'ir.attachment',
                method: 'try_remove',
                args: [],
                kwargs: {
                    ids: [id],
                    context: website.get_context()
                }
            }).then(function (prevented) {
                if (_.isEmpty(prevented)) {
                    self.records = _.without(self.records, attachment);
                    self.display_attachments();
                    return;
                }
                $both.css({borderWidth: "", borderColor: ""});
                $help_block.replaceWith(openerp.qweb.render(
                    'website.editor.dialog.image.existing.error', {
                        views: prevented[id]
                    }
                ));
            });
        },
    });

    website.editor.RTEImageDialog = website.editor.ImageDialog.extend({
        init: function (parent, editor, media) {
            this._super(parent, editor, media);
            this.on('start', this, this.proxy('started'));
            this.on('save', this, this.proxy('saved'));
        },
        started: function (holder) {
            if (!this.media) { this.media = document.getElementsByClassName('insert-media')[0]; }
            var el = this.media;
            if (!el) { return; }
            holder.url = el.getAttribute('src');
        },
        saved: function (data) {
            var element = document.getElementsByClassName('insert-media')[0];
            $('p').removeClass('insert-media');
            if (!(element = this.media)) {
                element = document.createElement('img');
                element.addClass('img');
                element.addClass('img-responsive');
                setTimeout(function () {
                    editor.insertElement(element);
                }, 0);
            }
            var style = data.style;
            element.setAttribute('src', data.url);
            if (style) { element.addClass(style); }
        },
    });

    function getCssSelectors(filter) {
        var classes = [];
        var sheets = document.styleSheets;
        for(var i = 0; i < sheets.length; i++) {
            var rules = sheets[i].rules || sheets[i].cssRules;
            for(var r = 0; r < rules.length; r++) {
                var selectorText = rules[r].selectorText;
                if (selectorText) {
                    var match = selectorText.match(filter);
                    if (match) classes.push(match[1].slice(1, match[1].length));
                }
            }
        }
        return classes;
    }

    website.editor.FontIconsDialog = website.editor.Media.extend({
        template: 'website.editor.dialog.font-icons',
        events : _.extend({}, website.editor.Dialog.prototype.events, {
            change: 'update_preview',
            'click .font-icons-icon': function (e) {
                e.preventDefault();
                e.stopPropagation();

                this.$('#fa-icon').val(e.target.getAttribute('data-id'));
                this.update_preview();
            },
            'click #fa-preview span': function (e) {
                e.preventDefault();
                e.stopPropagation();

                this.$('#fa-size').val(e.target.getAttribute('data-size'));
                this.update_preview();
            },
        }),
        // extract list of FontAwesome from the cheatsheet.
        icons: getCssSelectors(/(?=^|\s)(\.fa-[0-9a-z_-]+)/i).splice(22, Infinity),
        /*
         * Initializes select2: in Chrome and Safari, <select> font apparently
         * isn't customizable (?) and the fontawesome glyphs fail to appear.
         */
        start: function () {
            return this._super().then(this.proxy('load_data'));
        },
        search: function (needle) {
            var icons = this.icons;
            if (needle) {
                icons = _(icons).filter(function (icon) {
                    return icon.id.substring(3).indexOf(needle) !== -1;
                });
            }
            this.$('div.font-icons-icons').html(
                openerp.qweb.render(
                    'website.editor.dialog.font-icons.icons',
                    {icons: icons}));
        },
        /**
         * Removes existing FontAwesome classes on the bound element, and sets
         * all the new ones if necessary.
         */
        save: function () {
            if (! this.media){
                var $image = this.$el.find('.font-icons-selected');
                var rng = range.create()
                if($('.insert-media').length){
                    rng = document.createRange();
                    rng.selectNodeContents(document.getElementsByClassName('insert-media')[0])
                    $('p').removeClass('insert-media');
                }
                rng.insertNode($image[0]);
                $('.popover').hide();
            } else {
                var style = this.media.attributes.style ? this.media.attributes.style.textContent : '';
                var classes = (this.media.className||"").split(/\s+/);
                var non_fa_classes = _.reject(classes, function (cls) {
                    return cls === 'fa' || /^fa-/.test(cls);
                });
                var final_classes = non_fa_classes.concat(this.get_fa_classes());
                if (this.media.tagName !== "SPAN") {
                    var media = document.createElement('span');
                    $(this.media).replaceWith(media);
                    this.media = media;
                }
                $(this.media).attr("class", final_classes.join(' ')).attr("style", style);
            }
            this._super();
        },
        /**
         * Looks up the various FontAwesome classes on the bound element and
         * sets the corresponding template/form elements to the right state.
         * If multiple classes of the same category are present on an element
         * (e.g. fa-lg and fa-3x) the last one occurring will be selected,
         * which may not match the visual look of the element.
         */
        load_data: function () {
            var classes = (this.media&&this.media.className||"").split(/\s+/);
            for (var i = 0; i < classes.length; i++) {
                var cls = classes[i];
                switch(cls) {
                case 'fa-2x':case 'fa-3x':case 'fa-4x':case 'fa-5x':
                    // size classes
                    this.$('#fa-size').val(cls);
                    continue;
                case 'fa-spin':
                case 'fa-rotate-90':case 'fa-rotate-180':case 'fa-rotate-270':
                case 'fa-flip-horizontal':case 'fa-rotate-vertical':
                    this.$('#fa-rotation').val(cls);
                    continue;
                case 'fa-fw':
                    continue;
                case 'fa-border':
                    this.$('#fa-border').prop('checked', true);
                    continue;
                default:
                    if (!/^fa-/.test(cls)) { continue; }
                    this.$('#fa-icon').val(cls);
                }
            }
            this.update_preview();
        },
        /**
         * Serializes the dialog to an array of FontAwesome classes. Includes
         * the base ``fa``.
         */
        get_fa_classes: function () {
            return [
                'fa',
                this.$('#fa-icon').val(),
                this.$('#fa-size').val(),
                this.$('#fa-rotation').val(),
                this.$('#fa-border').prop('checked') ? 'fa-border' : ''
            ];
        },
        update_preview: function () {
            this.$preview.empty();
            var $preview = this.$('#fa-preview').empty();

            var sizes = ['fa-1x', 'fa-2x', 'fa-3x', 'fa-4x', 'fa-5x'];
            var classes = this.get_fa_classes();
            var no_sizes = _.difference(classes, sizes).join(' ');
            var selected = false;
            for (var i = sizes.length - 1; i >= 0; i--) {
                var size = sizes[i];

                var $p = $('<span>')
                        .attr('data-size', size)
                        .addClass(size)
                        .addClass(no_sizes);
                if ((size && _.contains(classes, size)) || (classes[2] === "" && !selected)) {
                    this.$preview.append($p.clone());
                    this.$('#fa-size').val(size);
                    $p.addClass('font-icons-selected');
                    selected = true;
                }
                $preview.prepend($p);
            }
        },
        clear: function () {
            this.media.className = this.media.className.replace(/(^|\s)(fa(\s|$)|fa-[^\s]*)/g, ' ');
        },
    });

    website.editor.VideoDialog = website.editor.Media.extend({
        template: 'website.editor.dialog.video',
        events : _.extend({}, website.editor.Dialog.prototype.events, {
            'click input#urlvideo ~ button': 'get_video',
            'click input#embedvideo ~ button': 'get_embed_video',
            'change input#urlvideo': 'change_input',
            'keyup input#urlvideo': 'change_input',
            'change input#embedvideo': 'change_input',
            'keyup input#embedvideo': 'change_input'
        }),
        start: function () {
            this.$iframe = this.$("iframe");
            var $media = $(this.media);
            if ($media.hasClass("media_iframe_video")) {
                var src = $media.data('src');
                this.$("input#urlvideo").val(src);
                this.$("#autoplay").attr("checked", src.indexOf('autoplay=1') != -1);
                this.get_video();
            }
            return this._super();
        },
        change_input: function (e) {
            var $input = $(e.target);
            var $button = $input.parent().find("button");
            if ($input.val() === "") {
                $button.addClass("btn-default").removeClass("btn-primary");
            } else {
                $button.removeClass("btn-default").addClass("btn-primary");
            }
        },
        get_url: function () {
            var video_id = this.$("#video_id").val();
            var video_type = this.$("#video_type").val();
            switch (video_type) {
                case "youtube":
                    return "//www.youtube.com/embed/" + video_id + "?autoplay=" + (this.$("#autoplay").is(":checked") ? 1 : 0);
                case "vimeo":
                    return "//player.vimeo.com/video/" + video_id + "?autoplay=" + (this.$("#autoplay").is(":checked") ? 1 : 0);
                case "dailymotion":
                    return "//www.dailymotion.com/embed/video/" + video_id + "?autoplay=" + (this.$("#autoplay").is(":checked") ? 1 : 0);
                default:
                    return video_id;
            }
        },
        get_embed_video: function (event) {
            event.preventDefault();
            var embedvideo = this.$("input#embedvideo").val().match(/src=["']?([^"']+)["' ]?/);
            if (embedvideo) {
                this.$("input#urlvideo").val(embedvideo[1]);
                this.get_video(event);
            }
            return false;
        },
        get_video: function (event) {
            if (event) event.preventDefault();
            var needle = this.$("input#urlvideo").val();
            var video_id;
            var video_type;

            if (needle.indexOf(".youtube.") != -1) {
                video_type = "youtube";
                video_id = needle.match(/\.youtube\.[a-z]+\/(embed\/|watch\?v=)?([^\/?&]+)/i)[2];
            } else if (needle.indexOf("//youtu.") != -1) {
                video_type = "youtube";
                video_id = needle.match(/youtube\.[a-z]+\/([^\/?&]+)/i)[1];
            } else if (needle.indexOf("player.vimeo.") != -1 || needle.indexOf("//vimeo.") != -1) {
                video_type = "vimeo";
                video_id = needle.match(/vimeo\.[a-z]+\/(video\/)?([^?&]+)/i)[2];
            } else if (needle.indexOf(".dailymotion.") != -1) {
                video_type = "dailymotion";
                video_id = needle.match(/dailymotion\.[a-z]+\/(embed\/)?(video\/)?([^\/?&]+)/i)[3];
            } else {
                video_type = "";
                video_id = needle;
            }

            this.$("#video_id").val(video_id);
            this.$("#video_type").val(video_type);

            this.$iframe.attr("src", this.get_url());
            return false;
        },
        save: function () {
            var video_id = this.$("#video_id").val();
            if (!video_id) {
                this.$("button.btn-primary").click();
                video_id = this.$("#video_id").val();
            }
            var video_type = this.$("#video_type").val();
            var $iframe = $(
                '<div class="media_iframe_video" data-src="'+this.get_url()+'">'+
                    '<div class="css_editable_mode_display">&nbsp;</div>'+
                    '<iframe src="'+this.get_url()+'" frameborder="0" allowfullscreen="allowfullscreen"></iframe>'+
                '</div>');
            $('.insert-media').replaceWith($iframe);
            $(this.media).replaceWith($iframe);
            this.media = $iframe[0];
            this._super();
        },
        clear: function () {
            delete this.media.dataset.src;
            this.media.className = this.media.className.replace(/(^|\s)media_iframe_video(\s|$)/g, ' ');
        },
    });
})();

