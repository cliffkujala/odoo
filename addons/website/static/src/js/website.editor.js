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
    /* Add method to Summernote
    * merge:
    *  - for every node (text or not) when mergeFilter return true by default mergeFilter is dom.mergeFilter
    *  - return {merged, sc, so, ec, eo}
    * removeSpace:
    *  - remove space but keep html space char (&nbsp;) ans all space in 'script' tag and node with 'pre' style
    *  - return {merged, sc, so, ec, eo}
    * pasteText:
    *  - paste text and convert into different 'p' tag .
    *  - Close the dom.pasteTextClose list for the parent node of the caret
    *  - All line are converted as 'p' tag by default or by parent node of the caret if the tag is a dom.pasteTextApply
    * reRange:
    *  - change the selected range in function off the reRangeFilter to don't break the dom items
    */

    dom.orderClass = function (node) {
        if (!node.className) return;
        var className = node.className.replace(/^\s+|\s+$/g, '').replace(/[\s\n\r]+/g, ' ').split(" ");
        if (!className.length) {
            node.removeAttribute("class");
            return;
        }
        className.sort();
        node.className = className.join(" ");
    };
    dom.isEqual = function (prev, cur) {
        if (prev.tagName !== cur.tagName) {
            return false;
        }
        if ((prev.attributes ? prev.attributes.length : 0) !== (cur.attributes ? cur.attributes.length : 0)) {
            return false;
        }

        function strip(text) {
            return text && text.replace(/^\s+|\s+$/g, '').replace(/\s+/g, ' ');
        }
        var att, att2;
        loop_prev:
        for(var a in prev.attributes) {
            att = prev.attributes[a];
            for(var b in cur.attributes) {
                att2 = cur.attributes[b];
                if (att.name === att2.name) {
                    if (strip(att.value) != strip(att2.value)) return false;
                    continue loop_prev;
                }
            }
            return false;
        }
        return true;
    };
    dom.mergeFilter = function (prev, cur) {
        if (prev && !prev.tagName && !cur.tagName) {
            return true;
        }
        if (prev && !cur.tagName && !cur.textContent.match(/\S/) && (!prev.tagName || prev.textContent.match(/\S/))) {
            return true;
        }
        if (prev && dom.isEqual(prev, cur) &&
            ((prev.tagName && "inline".indexOf(window.getComputedStyle(prev).display) !== -1 &&
              cur.tagName && "inline".indexOf(window.getComputedStyle(cur).display) !== -1))) {
            return true;
        }
        if (cur.tagName === "FONT" && !cur.attributes.getNamedItem('style')) {
            return true;
        }
        if (cur.tagName === "SPAN" && !cur.className) {
            return true;
        }
    };
    dom.doMerge = function (prev, cur) {
        if (prev.tagName) {
            if (cur.tagName) {
                while (cur.firstChild) {
                    prev.appendChild(cur.firstChild);
                }
                cur.parentNode.removeChild(cur);
            } else {
                prev.appendChild(cur);
            }
        } else {
            if (cur.tagName) {
                var deep = cur;
                while (deep.tagName && deep.firstChild) {deep = deep.firstChild;}
                prev.appendData(deep.textContent);
                cur.parentNode.removeChild(cur);
            } else {
                prev.appendData(cur.textContent);
                cur.parentNode.removeChild(cur);
            }
        }
    };
    dom.merge = function (node, begin, so, end, eo, mergeFilter, all) {
        mergeFilter = mergeFilter || dom.mergeFilter;
        var _merged = false;
        var add = all || false;

        if (!begin) {
            begin = node;
            while(begin.firstChild) {begin = begin.firstChild;}
            so = 0;
        }
        if (!end) {
            end = node;
            while(end.lastChild) {end = end.lastChild;}
            eo = end.textContent.length-1;
        }

        while (begin && begin.tagName && begin.firstChild) {begin = begin.firstChild;}
        while (end && end.tagName && begin.firstChild) {end = end.firstChild;}

        (function __merge (node) {
            var merged = false;
            var prev;
            for (var k=0; k<node.childNodes.length; k++) {
                var cur = node.childNodes[k];

                if (cur === begin) {
                    if (!all) add = true;
                }
                
                __merge(cur);
                dom.orderClass(cur);

                if (!add || !cur) continue;
                if (cur === end) {
                    if (!all) add = false;
                }

                // create the first prev value
                if (!prev) {
                    if (mergeFilter.call(dom, prev, cur)) {
                        for (var i=0; i<cur.childNodes.length; i++) {
                            cur.parentNode.insertBefore(cur.childNodes[i], cur);
                            k--;
                        }
                        cur.parentNode.removeChild(cur);
                    }
                    prev = cur;
                    continue;
                }

                // merge nodes
                if (mergeFilter.call(dom, prev, cur)) {
                    var p = prev;
                    var c = cur;
                    // compute prev/end and offset
                    if (prev.tagName) {
                        if (cur.tagName) {
                            if (cur === begin) begin = prev;
                            if (cur === end) end = prev;
                        }
                    } else {
                        if (cur.tagName) {
                            var deep = cur;
                            while (deep.tagName && deep.lastChild) {deep = deep.lastChild;}
                            if (deep === begin) {
                                so += prev.textContent.length;
                                begin = prev;
                            }
                            if (deep === end) {
                                eo += prev.textContent.length;
                                end = prev;
                            }
                        } else {
                            // merge text nodes
                            if (cur === begin) {
                                so += prev.textContent.length;
                                begin = prev;
                            }
                            if (cur === end) {
                                eo += prev.textContent.length;
                                end = prev;
                            }
                        }
                    }

                    dom.doMerge(p, c);

                    merged = true;
                    k--;
                    continue;
                }

                prev = cur;
            }

            // an other loop to merge the new shibbing nodes
            if (merged) {
                _merged = true;
                __merge(node);
            }
        })(node);

        return {
            merged: _merged,
            sc: begin,
            ec: end,
            so: so,
            eo: eo
        };
    };
    dom.removeSpace = function (node, begin, so, end, eo) {
        var removed = false;
        var offsetEnd = end && (end.textContent.length - eo);
        var add = node === begin;

        (function __remove_space (node) {
            if (!node) return;
            for (var k=0; k<node.childNodes.length; k++) {
                var cur = node.childNodes[k];

                if (cur === begin) add = true;

                if (cur.tagName && cur.tagName !== "SCRIPT" && cur.tagName !== "STYLE" && window.getComputedStyle(cur).whiteSpace !== "pre") {
                    __remove_space(cur);
                }

                if (!add) continue;
                if (cur === end) add = false;

                // remove begin empty text node
                if (node.childNodes.length > 1 && !cur.tagName && !cur.textContent.match(/\S/)) {
                    removed = true;
                    if (cur === begin) {
                        so -= cur.textContent.length;
                        begin = cur.parentNode;
                    }
                    if (cur === end) {
                        offsetEnd = 0;
                        end = cur.parentNode;
                    }
                    cur.parentNode.removeChild(cur);
                    while (begin.tagName && begin.lastChild) {begin = begin.lastChild;}
                    while (end.tagName && end.lastChild) {end = end.lastChild;}
                    k--;
                    continue;
                }

                // convert HTML space
                if (!cur.tagName) {
                    var text;
                    var exp1 = /[\t\n\r ]+/g;
                    var exp2 = /(?!([ ]|\u00A0)|^)\u00A0(?!([ ]|\u00A0)|$)/g;
                    if (cur === begin) {
                        var temp = cur.textContent.substr(0, so);
                        var _temp = temp.replace(exp1, ' ').replace(exp2, ' ');
                        so -= temp.length - _temp.length;
                    }
                    if (cur === end) {
                        var temp = cur.textContent.substr(-offsetEnd, cur.textContent.length);
                        var _temp = temp.replace(exp1, ' ').replace(exp2, ' ');
                        offsetEnd -= temp.length - _temp.length;
                    }
                    var text = cur.textContent.replace(exp1, ' ').replace(exp2, ' ');
                    removed = removed || cur.textContent.length !== text.length;
                    cur.textContent = text;
                }
            }
        })(node);

        return {
            removed: removed,
            sc: begin,
            ec: end,
            so: so > 0 ? so : 0,
            eo: end && end.textContent.length > offsetEnd ? end.textContent.length - offsetEnd : 0
        };
    };
    dom.pasteTextApply = "h1 h2 h3 h4 h5 h6 li".split(" ");
    dom.pasteTextClose = "h1 h2 h3 h4 h5 h6 p b bold i u code sup strong small li pre".split(" ");
    dom.pasteText = function (textNode, offset, text, isOnlyText) {
        // clean the node
        var data = dom.merge(textNode.parentElement.parentElement, textNode, offset, textNode, offset, null, true);
        var node = textNode.parentNode;
        data = dom.removeSpace(textNode.parentElement.parentElement, data.sc, data.so, data.ec, data.eo);
        while(!node.tagName) {node = node.parentNode;}
        // Break the text node up
        if (data.sc.tagName) {
            if (data.sc.tagName.toLowerCase() === "br") {
                data.sc = data.sc.parentNode.insertBefore(document.createTextNode(" "), data.sc);
            } else if (data.sc.firstChild) {
                data.sc = data.sc.insertBefore(document.createTextNode(" "), data.sc.firstChild);
            } else {
                data.sc = data.sc.appendChild(document.createTextNode(" "));
            }
            data.so = 0;
        }
        data.sc.splitText(data.so);
        node = data.sc.parentNode;
        var first = data.sc;
        var last = data.sc.nextSibling;

        isOnlyText = isOnlyText || !text.match('\n');
        
        if (!isOnlyText) {
            // tag to close and open
            var tag = node.tagName.toLowerCase();
            if(dom.pasteTextApply.indexOf(tag) === -1) {
                text = "<p>"+text.split('\n').join("</p><p>")+"</p>";
            } else {
                text = "<"+tag+">"+text.split('\n').join("</"+tag+"><"+tag+">")+"</"+tag+">";
            }

            var $text = $(text);

            // split parent node and insert text
            if(dom.pasteTextClose.indexOf(tag) !== -1) {
                var $next = $(node).clone().empty();
                $next.append( last );
                $(node).after( $next );
                $(node).after( $text );
            } else {
                $(data.sc).after( $text );
            }
        } else {
            first.appendData( text );
        }

        // clean the dom content
        data = dom.merge(node.parentElement.parentElement, last, 0, last, 0, null, true);
        data = dom.removeSpace(node.parentElement.parentElement, data.sc, data.so, data.ec, data.eo);

        // move caret
        range.create(data.sc, data.so, data.ec, data.eo).select();
    };

    var fn_rc = range.create;
    range.create = function (sc, so, ec, eo) {
        var wrappedRange = fn_rc.apply(this, arguments);
        if (!wrappedRange) return;
        wrappedRange.clean = function (mergeFilter) {
            var node = this.sc === this.ec ? this.sc : this.commonAncestor();
            if (node.childNodes.length <=1) {
                return this;
            }

            var merge = dom.merge(node, this.sc, this.so, this.ec, this.eo, mergeFilter);
            var rem = dom.removeSpace(node, this.sc, merge.so, this.ec, merge.eo);

            if (merge.merged || rem.removed) {
                return range.create(rem.sc, rem.so, merge.ec, rem.eo);
            }
            return this;
        };
        return wrappedRange;
    };
    range.reRangeFilter = function () { return true; };
    range.reRange = function (sc, so, ec, eo, keep_end) {
        // search the first snippet editable node
        var start = keep_end ? ec : sc;
        while (start) {
            if ($(start).filter(range.reRangeFilter).length) {
                break;
            }
            start = start.parentNode;
        }

        // check if the end caret have the same node
        var lastFilterEnd;
        var end = keep_end ? sc : ec;
        while (end) {
            if (start === end) {
                break;
            }
            if ($(end).filter(range.reRangeFilter).length) {
                lastFilterEnd = end;
            }
            end = end.parentNode;
        }
        if (lastFilterEnd) {
            end = lastFilterEnd;
        }
        if (!end) {
            end = document.getElementsByTagName('body')[0];
        }

        // if same node, keep range
        if (start === end || !start) {
            return range.create(sc, so, ec, eo);
        }

        // reduce or extend the range to don't break a reRangeFilter area
        if ($.contains(start, end)) {

            if (keep_end) {
                while (!end.previousElementSibling) {
                    end = end.parentNode;
                }
                sc = end.previousElementSibling;
                while (sc.lastChild) {
                    sc = sc.lastChild;
                }
                so = sc.textContent.length;
            } else {
                while (!end.nextElementSibling) {
                    end = end.parentNode;
                }
                ec = end.nextElementSibling;
                while (ec.firstChild) {
                    ec = ec.firstChild;
                }
                eo = 0;
            }
        } else {

            if (keep_end) {
                sc = start;
                while (sc.firstChild) {
                    sc = sc.firstChild;
                }
                so = 0;
            } else {
                ec = start;
                while (ec.lastChild) {
                    ec = ec.lastChild;
                }
                eo = ec.textContent.length;
            }
        }

        return range.create(sc, so, ec, eo);
    };

    //////////////////////////////////////////////////////////////////////////////////////////////////////////
    /* add some text commands */

    key.nameFromCode[46] = 'DELETE';
    key.nameFromCode[27] = 'ESCAPE';

    settings.options.keyMap.pc['BACKSPACE'] = 'backspace';
    settings.options.keyMap.pc['DELETE'] = 'delete';
    settings.options.keyMap.pc['ENTER'] = 'enter';
    settings.options.keyMap.pc['ESCAPE'] = 'cancel';

    settings.options.keyMap.mac['BACKSPACE'] = 'backspace';
    settings.options.keyMap.mac['CMD+BACKSPACE'] = 'delete';
    settings.options.keyMap.mac['ENTER'] = 'enter';
    settings.options.keyMap.mac['ESCAPE'] = 'cancel';

    function clean_dom_onkeydown () {
        setTimeout(function () {
            var r = range.create();
            if (!r) return;
            var parent = r.sc.parentElement.parentElement;
            r = dom.merge(parent, r.sc, r.so, r.sc, r.so, null, true);
            r = dom.removeSpace(parent, r.sc, r.so, r.sc, r.so);
            if (r.ec.tagName === "BR") {
                r.sc = r.ec = r.sc.previousSibling || r.sc.parentNode;
            }
            r.eo = r.eo > r.ec.textContent.length ? r.ec.textContent.length : r.eo;
            if (r.so > r.eo) r.so = r.eo;
            range.create(r.sc, r.so, r.ec, r.eo).select();
        },0);
    }
    
    var mergeOnDelete = "h1 h2 h3 h4 h5 h6 p b bold i u code sup strong small li a ul ol".split(" ");
    var forbiddenWrite = ".fa img".split(" ");

    eventHandler.editor.tab = function ($editable, options, outdent) {
        var r = range.create();
        var outdent = outdent || false;

        if (r.isCollapsed()) {
            if (r.isOnCell()) {
                this.table.tab(r, outdent);
                return false;
            }
            if (r.so) {
                if (!outdent){
                    var next = r.sc.splitText(r.so);
                    this.insertTab($editable, r, options.tabsize);
                    r = range.create(next, 0, next, 0);
                    r = dom.merge(r.sc.parentNode, r.sc, r.so, r.ec, r.eo, null, true);
                    range.create(r.sc, r.so, r.ec, r.eo).select();
                } else {
                    r = dom.merge(r.sc.parentNode, r.sc, r.so, r.ec, r.eo, null, true);
                    r = range.create(r.sc, r.so, r.ec, r.eo);
                    var next = r.sc.splitText(r.so);
                    r.sc.textContent = r.sc.textContent.replace(/(\u00A0)+$/g, '');
                    next.textContent = next.textContent.replace(/^(\u00A0)+/g, '');
                    range.create(r.sc, r.sc.textContent.length, r.sc, r.sc.textContent.length).select();
                }
                return false;
            }
        }

        if (outdent) {
            this.outdent($editable);
        } else {
            this.indent($editable);
        }
    };
    eventHandler.editor.untab = function ($editable, options) {
        var r = range.create();
        if (r.isCollapsed() && r.isOnCell()) {
            this.table.tab(r, true);
        }
        this.tab($editable, options, true);
    };
    eventHandler.editor.enter = function ($editable, options) {
        $editable.data('NoteHistory').recordUndo($editable, "visible");
        
        var r = range.create();
        if (!r.isCollapsed()) {
            return false;
        }

        if (!r.sc.tagName) return true;
        var $node = $(r.sc);
        var clone = $node.clone()[0];
        $node.after(clone);
        range.createFromNode(clone).select();
    };
    eventHandler.editor.visible = function ($editable, options) {
        $editable.data('NoteHistory').recordUndo($editable, "visible");
        
        var r = range.create();
        var node = r.sc;
        var needChange = false;
        while (node.parentNode) {
            if ($(node).is(forbiddenWrite.join(","))) {
                needChange = true;
                break;
            }
            node = node.parentNode;
        }

        if (needChange) {
            var text = node.previousSibling;
            if (text && !text.tagName && text.textContent.match(/\S/)) {
                range.create(text, text.textContent.length, text, text.textContent.length).select();
            } else {
                text = node.parentNode.insertBefore(document.createTextNode( "_ " ), node);
                range.create(text, 0, text, 0).select();
                setTimeout(function () {
                    var text = range.create().sc;
                    text.textContent = text.textContent.replace(/_ $/, ' ');
                    range.create(text, text.textContent.length-1, text, text.textContent.length-1).select();
                },0);
            }
        }
        return true;
    };
    eventHandler.editor.delete = function ($editable, options) {
        $editable.data('NoteHistory').recordUndo($editable, "delete");
        
        var r = range.create();
        if (!r || !r.isCollapsed()) {
            return true;
        }
        var node = r.ec;
        while (!node.nextSibling && !node.previousSibling) {node = node.parentNode;}
        
        var content = r.ec.textContent.replace(/\s+$/, '');

        // empty tag
        if (r.sc===r.ec && !content.length && node.nextSibling) {
            var next = node.nextSibling;
            while (next.tagName && next.firstChild) {next = next.firstChild;}
            node.parentNode.removeChild(node);
            range.create(next, 0, next, 0).select();
        }
        // normal feature if same tag and not the end
        else if (r.sc===r.ec && r.eo<content.length && content.match(/\S/)) return true;
        // merge with the next text node
        else if (r.ec.nextSibling && !r.ec.nextSibling.tagName) return true;
        // jump to next node for delete
        else if (r.sc.nextSibling) {
            node = r.sc.nextSibling;
            while (node.firstChild) {
                node = node.firstChild;
            }
            r = range.create(node, node.textContent.length, node, node.textContent.length);
            r.select();
            return this.delete($editable, options);
        }
        //merge with the next block
        else if (r.isCollapsed() && r.eo>=content.length && mergeOnDelete.indexOf(r.ec.parentNode.tagName.toLowerCase()) !== -1) {

            summernote_keydown_clean("ec");
            var next = r.ec.parentNode.nextElementSibling;
            var style = window.getComputedStyle(next);

            if (next && (r.sc.parentNode.tagName === next.tagName || style.display !== "block" || !parseInt(style.height))) {

                dom.doMerge(r.sc.parentNode, next);
                range.create(r.sc, r.so, r.sc, r.so).select();

            } else {
                var check = false;
                var node = r.sc;
                var nodes = [node];

                do {
                    nodes.push(node);
                    node = node.parentNode;
                    if (node.nextElementSibling) {
                        if (node.nextElementSibling.tagName === node.tagName) {
                            nodes.push(node);
                        }
                        break;
                    }
                }  while (node && mergeOnDelete.indexOf(node.tagName.toLowerCase()) !== -1);

                while (nodes.length) {
                    node = nodes.pop();
                    if (node && node.nextElementSibling && node.nextElementSibling.tagName === node.tagName) {
                        dom.doMerge(node, node.nextElementSibling);
                    }
                }
                range.create(r.ec, r.ec.textContent.length, r.ec, r.ec.textContent.length).select();
            }
        }
        clean_dom_onkeydown();
        return false;
    };
    eventHandler.editor.backspace = function ($editable, options) {
        $editable.data('NoteHistory').recordUndo($editable, "backspace");

        var r = range.create();
        if (!r || !r.isCollapsed()) {
            return true;
        }
        var node = r.sc;
        while (!node.nextSibling && !node.previousSibling) {node = node.parentNode;}
        
        // empty tag
        if (r.sc===r.ec && !r.sc.textContent.replace(/\s+$/, '').length && node.previousSibling) {
            var next = node.previousSibling;
            while (next.tagName && next.lastChild) {next = next.lastChild;}
            node.parentNode.removeChild(node);
            range.create(next, next.textContent.length, next, next.textContent.length).select();
        }
        // normal feature if same tag and not the begin
        else if (r.sc===r.ec && r.so || r.eo) return true;
        // merge with the previous text node
        else if (r.sc.previousSibling && !r.sc.previousSibling.tagName) return true;
        // jump to previous node for delete
        else if (r.sc.previousSibling) {
            node = r.sc.previousSibling;
            while (node.lastChild) {
                node = node.lastChild;
            }
            r = range.create(node, node.textContent.length, node, node.textContent.length);
            r.select();
            return this.backspace($editable, options);
        }
        //merge with the previous block
        else if (r.isCollapsed() && !r.eo && mergeOnDelete.indexOf(r.sc.parentNode.tagName.toLowerCase()) !== -1) {

            summernote_keydown_clean("sc");
            var prev = r.sc.parentNode.previousElementSibling;
            var style = window.getComputedStyle(prev);

            if (prev && (r.sc.parentNode.tagName === prev.tagName || style.display !== "block" || !parseInt(style.height))) {

                dom.doMerge(prev, r.sc.parentNode);
                range.create(r.sc, 0, r.sc, 0).select();

            } else {
                var check = false;
                var node = r.sc;
                var nodes = [node];

                do {
                    nodes.push(node);
                    node = node.parentNode;
                    if (node.previousElementSibling) {
                        if (node.previousElementSibling.tagName === node.tagName) {
                            nodes.push(node);
                        }
                        break;
                    }
                }  while (node && mergeOnDelete.indexOf(node.tagName.toLowerCase()) !== -1);

                while (nodes.length) {
                    node = nodes.pop();
                    if (node && node.previousElementSibling && node.previousElementSibling.tagName === node.tagName) {
                        dom.doMerge(node.previousElementSibling, node);
                    }
                }
                range.create(r.sc, 0, r.sc, 0).select();
            }
        }

        clean_dom_onkeydown();
        return false;
    };
    var fn_editor_fontSize = eventHandler.editor.fontSize;
    eventHandler.editor.fontSize = function ($editable, sValue) {
        fn_editor_fontSize.call(this, $editable, sValue);
        var r = range.create();
        var ancestor = dom.commonAncestor(r.sc, r.ec);
        var $fonts = $(ancestor).find('font, span');
        if (!$fonts.length) {
            $fonts = $(ancestor).closest('font, span');
        }

        $fonts.each(function () {
            $(this).removeAttr('size');

            $(this).css('font-size', parseInt(window.getComputedStyle(this).fontSize) != sValue ? sValue + 'px' : null);
        });

        r = dom.merge($fonts.parent()[0], r.sc, r.so, r.ec, r.eo, null, true);
        range.create(r.sc, r.so, r.ec, r.eo).select();
    };

    //////////////////////////////////////////////////////////////////////////////////////////////////////////
    /* add list command (create a uggly dom for chrome) */

    function isFormatNode(node) {
        return node.tagName && settings.options.styleTags.indexOf(node.tagName.toLowerCase()) !== -1;
    }

    eventHandler.editor.insertUnorderedList = function ($editable, sorted) {
        history.recordUndo($editable);

        var rng = range.create();
        var node = rng.sc;
        while (node && node !== $editable[0]) {
            if (node.tagName === (sorted ? "UL" : "OL")) {

                var ul = document.createElement(sorted ? "ol" : "ul");
                ul.className = node.className;
                node.parentNode.insertBefore(ul, node);
                while (node.firstChild) {
                    ul.appendChild(node.firstChild);
                }
                node.parentNode.removeChild(node);
                rng.select();
                return;

            } else if (node.tagName === (sorted ? "OL" : "UL")) {

                var lis = $(node).find("li").get();
                _.each(lis, function (li) {
                    while (li.firstChild) {
                        node.parentNode.insertBefore(li.firstChild, node);
                    }
                });
                node.parentNode.removeChild(node);
                rng.select();
                return;

            }
            node = node.parentNode;
        }

        var p0 = rng.sc;
        while (p0 && p0 !== $editable[0] && !isFormatNode(p0)) {
            p0 = p0.parentNode;
        }
        if (!p0) return;
        var p1 = rng.ec;
        while (p1 && p1 !== $editable[0] && !isFormatNode(p1)) {
            p1 = p1.parentNode;
        }
        if (p0.parentNode !== p1.parentNode) return;

        var parent = p0.parentNode;
        var ul = document.createElement(sorted ? "ol" : "ul");
        var childNodes = parent.childNodes;
        parent.insertBefore(ul, p0);
        for (var i=0; i<childNodes.length; i++) {
            if (!isFormatNode(childNodes[i]) || (!ul.firstChild && childNodes[i] !== p0)) {
                continue;
            }
            var li = document.createElement('li');
            ul.appendChild(li);
            li.appendChild(childNodes[i]);
            if (li.firstChild === p1) {
                break;
            }
            i--;
        }
        rng.select();
    };
    eventHandler.editor.insertOrderedList = function ($editable) {
        this.insertUnorderedList($editable, true);
    };
    eventHandler.editor.indent = function ($editable, outdent) {
        history.recordUndo($editable);
        var r = range.create();

        var flag = false;
        function indentUL (UL, start, end) {
            var tagName = UL.tagName;
            var className = UL.className;
            var node = UL.firstChild;
            var ul = UL;
            var li;

            // search the first
            while (node && !flag) {
                if (node === start || $.contains(node, start)) {
                    flag = true;
                    break;
                }
                node = node.nextElementSibling;
            }

            if (!flag) {
                return;
            }

            // add li into the indented ul
            if (node.previousElementSibling) {
                ul = document.createElement(tagName);

                while (node && flag) {
                    li = node;
                    node = node.nextElementSibling;
                    if (li === end || $.contains(li, end)) {
                        ul.appendChild(li);
                        flag = false;
                        break;
                    }
                    ul.appendChild(li);
                }
                if (UL.nextSibling) {
                    UL.parentNode.insertBefore(ul, UL.nextSibling);
                } else {
                    UL.parentNode.appendChild(ul);
                }
            } else {
                while (node) {
                    li = node;
                    node = node.nextElementSibling;
                    if (li === end || $.contains(li, end)) {
                        flag = false;
                        break;
                    }
                }
            }

            if (className.length) {
                ul.className = className.replace(/indent([0-9])/, function (a,b,c) {
                        var num = (b ? +b : 0 ) + (outdent ? -1 : 1);
                        return 'indent' + (num < 0 ? 0 : (num > 6 ? 6 : num));
                    }).replace(/\s*indent0/, '');

                if (!ul.className.length) {
                    ul.removeAttribute("class");
                }
            } else {
                ul.className += ' indent1';
            }

            // insert the rest of the non-indented ul
            if (node) {
                var UL2 = document.createElement(tagName);
                if (className.length) {
                    UL2.className = className;
                } else {
                    UL2.removeAttribute("class");
                }

                while (node) {
                    li = node;
                    node = node.nextElementSibling;
                    UL2.appendChild(li);
                }

                if (ul.nextElementSibling) {
                    ul.parentNode.insertBefore(UL2, ul.nextSibling);
                } else {
                    ul.parentNode.appendChild(UL2);
                }
            }
        }
        function indentOther (dom, start, end) {
            flag = true;
            if (dom.className.match(/indent([0-9])/)) {
                dom.className = dom.className.replace(/indent([0-9])/, function (a,b,c) {
                    var num = (b ? +b : 0 ) + (outdent ? -1 : 1);
                    if (!num) return "";
                    return 'indent' + (num > 6 ? 6 : num);
                });
            } else if(!outdent) {
                dom.className = (dom.className || "") + ' indent1';
            }
            if ($.contains(dom, end)) {
                flag = false;
            }
        }

        var ancestor = dom.commonAncestor(r.sc, r.ec);
        var $dom = $(ancestor);

        if (!$(ancestor).is("ul, ol")) {
            $dom = $(ancestor).children();
        }
        if (!$dom.length) {
            $dom = $(r.sc).closest("ul, ol");
            if (!$dom.length) {
                $dom = $(r.sc).closest(settings.options.styleTags.join(','));
            }
        }

        $dom.each(function () {
            if (flag || $.contains(this, r.sc)) {
                if (this.tagName === "UL" || this.tagName === "OL") {
                    indentUL(this, r.sc, r.ec);
                } else if (isFormatNode(this)) {
                    indentOther(this, r.sc, r.ec);
                }
            }
        });

        if ($dom.length) {
            var $parent = $dom.parent();

            // remove text nodes between lists
            var $ul = $parent.find('ul, ol');
            if (!$ul.length) {
                $ul = $(r.sc).closest("ul, ol");
            }
            $ul.each(function () {
                if (this.previousSibling &&
                    this.previousSibling !== this.previousElementSibling &&
                    !this.previousSibling.textContent.match(/\S/)) {
                    this.parentNode.removeChild(this.previousSibling);
                }
                if (this.nextSibling &&
                    this.nextSibling !== this.nextElementSibling &&
                    !this.nextSibling.textContent.match(/\S/)) {
                    this.parentNode.removeChild(this.nextSibling);
                }
            });

            // merge same ul or ol
            r = dom.merge($parent[0], r.sc, r.so, r.ec, r.eo, function (prev, cur) {
                    if (prev && (prev.tagName === "UL" || prev.tagName === "OL") && dom.isEqual(prev, cur)) {
                        return true;
                    }
                }, true);
            range.create(r.sc, r.so, r.ec, r.eo).select();
        }
    };
    eventHandler.editor.outdent = function ($editable) {
        this.indent($editable, true);
    };

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
        var $padding = $('<div class="o_undo btn-group"/>');
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
        var $imageprop = $('<div class="o_image btn-group"/>');
        $imageprop.appendTo($imagePopover.find('.popover-content'));
        $(renderer.tplIconButton('fa fa-picture-o', {
                title: _t('Edit'),
                event: 'showImageDialog'
            })).appendTo($imageprop);
        $(renderer.tplIconButton('fa fa-trash-o', {
                title: _t('Remove'),
                event: 'delete'
            })).appendTo($imageprop);

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

        //////////////// history Undo & Redo

        var $prevnext = $('<div class="o_undo btn-group"/>');
        var $prev = $(renderer.tplIconButton('fa fa-undo', {
                title: _t('Undo'),
                event: 'history',
                value: 'previous'
            }))
            .appendTo($prevnext);
        var $next = $(renderer.tplIconButton('fa fa-repeat', {
                title: _t('Redo'),
                event: 'history',
                value: 'next'
            }))
            .appendTo($prevnext);

        $imagePopover.find('.popover-content').append($prevnext);
        $linkPopover.find('.popover-content').append($prevnext.clone());
        $airPopover.find('.popover-content').append($prevnext.clone());

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

        $popover.children().css('z-index', 1040);

        fn_popover_update.call(this, $popover, oStyle, isAirMode);

        if (!$popover.data('loaded')) {
            summernote_popover_update ($popover);
            $popover.data('loaded', true);
        }

        $('.o_undo button:has(.fa-undo)').attr('disabled', !history.hasUndo());
        $('.o_undo button:has(.fa-repeat)').attr('disabled', !history.hasRedo());

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

        if (oStyle.anchor && ($airPopover.is(':visible') || (oStyle.image && !$(oStyle.image).closest('a').length))) {
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
        $('.o_undo button:has(.fa-undo)').attr('disabled', !history.hasUndo());
        $('.o_undo button:has(.fa-repeat)').attr('disabled', !history.hasRedo());
    });

    eventHandler.editor.undo = function ($popover) {
        if(!$popover.attr('disabled')) history.undo();
    };
    eventHandler.editor.redo = function ($popover) {
        if(!$popover.attr('disabled')) history.redo();
    };
    eventHandler.editor.cancel = function ($popover) {
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
    };
    eventHandler.editor.resize = function ($editable, sValue, $target) {
        $editable.data('NoteHistory').recordUndo($editable);
        switch (+sValue) {
            case 1: $target.toggleClass('img-responsive').removeClass('img-responsive-50 img-responsive-25'); break;
            case 0.5: $target.toggleClass('img-responsive-50').removeClass('img-responsive img-responsive-25'); break;
            case 0.25: $target.toggleClass('img-responsive-25').removeClass('img-responsive img-responsive-50'); break;
        }
        setTimeout(function () { $target.trigger("mouseup"); },0);
    };
    eventHandler.editor.floatMe = function ($editable, sValue, $target) {
        $editable.data('NoteHistory').recordUndo($editable);
        switch (sValue) {
            case 'center': $target.toggleClass('center-block').removeClass('pull-right pull-left'); break;
            case 'left': $target.toggleClass('pull-left').removeClass('pull-right center-block'); break;
            case 'right': $target.toggleClass('pull-right').removeClass('pull-left center-block'); break;
        }
        setTimeout(function () { $target.trigger("mouseup"); },0);
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
    function summernote_paste (event) {
        // keep norma feature if copy a picture
        var clipboardData = event.originalEvent.clipboardData;
        if (clipboardData.items) {
            var item = list.last(clipboardData.items);
            var isClipboardImage = item.kind === 'file' && item.type.indexOf('image/') !== -1;
            if (isClipboardImage) {
                return true;
            }
        }

        var $editable = $(event.currentTarget);
        $editable.data('NoteHistory').recordUndo($editable);

        event.preventDefault();
        var r = range.create();
        dom.pasteText(r.sc, r.so, clipboardData.getData("text/plain"));
        return false;
    }
    function summernote_keydown_clean (field) {
        setTimeout(function () {
            var r = range.create();
            var node = r[field];
            while (!node.tagName) {node = node.parentNode;}
            node = node.parentNode;
            var data = dom.merge(node, r.sc, r.so, r.ec, r.eo, null, true);
            data = dom.removeSpace(node, data.sc, data.so, data.sc, data.so);

            range.create(data.sc, data.so, data.sc, data.so).select();
        },0);
    }
    var cursor_mousedown;
    function summernote_mouseup (event) {
        if ($(event.target).closest("#website-top-navbar, .note-popover, .o_undo").length) {
            return;
        }
        // don't rerange if simple click
        if (!cursor_mousedown || 10 < Math.pow(cursor_mousedown.clientX-event.clientX, 2)+Math.pow(cursor_mousedown.clientY-event.clientY, 2) ) {
            reRangeSelect(event);
        }
    }
    function summernote_mousedown (event) {
        cursor_mousedown = event;
        var $btn = $(event.target).closest('.note-popover, .o_undo');
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
        if (!$(event.srcElement).closest('.o_undo, .note-editable, .note-popover, .note-link-dialog, .note-image-dialog, .note-air-dialog').length) {
            $(".note-popover > *").hide();
        }
    }
    var fn_attach = eventHandler.attach;
    eventHandler.attach = function (oLayoutInfo, options) {
        fn_attach.call(this, oLayoutInfo, options);
        oLayoutInfo.editor.on("paste", summernote_paste);
        oLayoutInfo.editor.on('dragstart', 'img', function (e) { e.preventDefault(); });
        $(document).on('mousedown', summernote_mousedown);
        $(document).on('mouseup', summernote_mouseup);
        $(document).on('click', summernote_click);
        oLayoutInfo.editor.on('dblclick', 'img', function (event) {
            new website.editor.MediaDialog(oLayoutInfo.editor, event.target).appendTo(document.body);
        });
    };
    var fn_dettach = eventHandler.dettach;
    eventHandler.dettach = function (oLayoutInfo, options) {
        fn_dettach.call(this, oLayoutInfo, options);
        oLayoutInfo.editor.off("paste", summernote_paste);
        oLayoutInfo.editor.off("dragstart");
        $(document).off('mousedown', summernote_mousedown);
        $(document).off('mouseup', summernote_mouseup);
        $(document).off('click', summernote_click);
        oLayoutInfo.editor.off("dblclick");
    };

    //////////////////////////////////////////////////////////////////////////////////////////////////////////
    /* Change History to have a global History for all summernote instances */

    var History = function History () {
        function re_enable_snippet (r) {
            $("#wrapwrap").trigger("click");
            $(".oe_overlay").remove();
            $("#wrapwrap *").filter(function () {
                var $el = $(this);
                if($el.data('snippet-editor')) {
                    $el.removeData();
                }
            });

            setTimeout(function () {
                $(r.sc.tagName ? r.sc : r.sc.parentNode).trigger("click");
            },0);
        }

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
            $editable.html(oSnap.contents).scrollTop(oSnap.scrollTop);
            var r = range.createFromBookmark($editable[0], oSnap.bookmark);
            re_enable_snippet(r);
            r.select();
        };

        this.undo = function ($editable) {
            if (!pos) { return; }
            last = null;
            if (!aUndo[pos]) aUndo[pos] = this.makeSnap($editable || $('.o_editable.note-editable:first'));
            this.applySnap(aUndo[--pos]);
        };
        this.hasUndo = function ($editable) {
            return pos > 0;
        };

        this.redo = function () {
            if (aUndo.length <= pos+1) { return; }
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
                if (event === last) return;
                else last = event;
            }
            aUndo.splice(pos, aUndo.length);
            aUndo[pos] = this.makeSnap($editable);
            pos++;
        };
    };
    var history = new History();

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

        $(document).on('submit', '.note-editable form', function (ev) {
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

            observer.disconnect();
            var defs = $('.o_editable')
                .filter('.o_dirty')
                .removeAttr('contentEditable')
                .removeClass('o_dirty o_editable cke_focus oe_carlos_danger')
                .map(function () {
                    var $el = $(this);

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
                        failure.error.message = '<b>' + data[0] + '</b><br/>' + data[1];
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
        tableNavigation: function (root) {
            var self = this;
            $('.o_editable').on('keydown', function (e) {
                // ignore non-TAB
                if (e.which !== 9) { return; }

                if (self.handleTab(e)) {
                    e.preventDefault();
                }
            });
        },
        /**
         * Performs whatever operation is necessary on a [TAB] hit, returns
         * ``true`` if the event's default should be cancelled (if the TAB was
         * handled by the function)
         */
        handleTab: function (event) {
            var forward = !event.shiftKey;

            var root = window.getSelection().getRangeAt(0).commonAncestorContainer;
            var $cell = $(root).closest('td,th');

            if (!$cell.length) { return false; }

            var cell = $cell[0];

            // find cell in same row
            var row = cell.parentNode;
            var sibling = row.cells[cell.cellIndex + (forward ? 1 : -1)];
            if (sibling) {
                document.getSelection().selectAllChildren(sibling);
                return true;
            }

            // find cell in previous/next row
            var table = row.parentNode;
            var sibling_row = table.rows[row.rowIndex + (forward ? 1 : -1)];
            if (sibling_row) {
                var new_cell = sibling_row.cells[forward ? 0 : sibling_row.cells.length - 1];
                document.getSelection().selectAllChildren(new_cell);
                return true;
            }

            // at edge cells, copy word/openoffice behavior: if going backwards
            // from first cell do nothing, if going forwards from last cell add
            // a row
            if (forward) {
                var row_size = row.cells.length;
                var new_row = document.createElement('tr');
                while(row_size--) {
                    var newcell = document.createElement('td');
                    // zero-width space
                    newcell.textContent = '\u200B';
                    new_row.appendChild(newcell);
                }
                table.appendChild(new_row);
                document.getSelection().selectAllChildren(new_row.cells[0]);
            }

            return true;
        },
        /**
         * Add a record undo to history
         * @param {DOM} target where the dom is changed is editable zone
         */
        historyRecordUndo: function ($target) {
            var $editable = $target.is('[data-oe-model]') ? $target : $target.closest('[data-oe-model]');
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

                    if (!range.create()) {
                        range.create($editable[0].firstChild || $editable[0],0,$editable[0].firstChild || $editable[0],0).select();
                    }
                }
            });

            $('#wrapwrap [data-oe-model]')
                .not('link, script')
                .not('img[data-oe-field="arch"], br[data-oe-field="arch"], input[data-oe-field="arch"]')
                .not('.oe_snippet_editor')
                .addClass('o_editable');

            $('#wrapwrap').on('click', '*', function (event) {
                event.preventDefault();
            });

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
                this.tableNavigation();
            }

            self.trigger('rte:ready');
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

            if (test !== false && (!val || !$e[0].checkValidity())) {
                // FIXME: error message
                $e.closest('.form-group').addClass('has-error');
                $e.focus();
                def.reject();
            }

            var style = this.$("input[name='link-style-type']:checked").val();
            var size = this.$("input[name='link-style-size']:checked").val();
            var classes = (style && style.length ? "btn " : "") + style + " " + size;

            var done = $.when();
            if ($e.hasClass('email-address') && $e.val().indexOf("@") !== -1) {
                def.resolve('mailto:' + val, false, label, classes);
            } else if ($e.val() && $e.val().length && $e.hasClass('page')) {
                var data = $e.select2('data');
                if (!data.create) {
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
                    self.data.isNewWindow = new_window;
                    self.data.text = label;
                    self.data.className = classes;

                    self.trigger("save", self.data);
                }).then(_super);
        },
        bind_data: function () {
            var href = this.data.url;
            var new_window = this.data.isNewWindow;
            var text = this.data.text;
            var classes = this.data.className = $(this.data.range.sc).attr("class");

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
            this.get_data(false).then(function (url, new_window, label, classes) {
                $preview.attr("target", new_window ? '_blank' : "")
                    .text((label && label.length ? label : url))
                    .attr("class", classes);
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
                this.media.className = "img-responsive pull-right";
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
            if (!this.media) { this.media = document.getElementsByClassName('insert-media')[0] }
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
        // List of FontAwesome icons in 4.0.3, extracted from the cheatsheet.
        // Each icon provides the unicode codepoint as ``text`` and the class
        // name as ``id`` so the whole thing can be fed directly to select2
        // without post-processing and do the right thing (except for the part
        // where we still need to implement ``initSelection``)
        // TODO: add id/name to the text in order to allow FAYT selection of icons?
        icons: [{"text": "\uf000", "id": "fa-glass"}, {"text": "\uf001", "id": "fa-music"}, {"text": "\uf002", "id": "fa-search"}, {"text": "\uf003", "id": "fa-envelope-o"}, {"text": "\uf004", "id": "fa-heart"}, {"text": "\uf005", "id": "fa-star"}, {"text": "\uf006", "id": "fa-star-o"}, {"text": "\uf007", "id": "fa-user"}, {"text": "\uf008", "id": "fa-film"}, {"text": "\uf009", "id": "fa-th-large"}, {"text": "\uf00a", "id": "fa-th"}, {"text": "\uf00b", "id": "fa-th-list"}, {"text": "\uf00c", "id": "fa-check"}, {"text": "\uf00d", "id": "fa-times"}, {"text": "\uf00e", "id": "fa-search-plus"}, {"text": "\uf010", "id": "fa-search-minus"}, {"text": "\uf011", "id": "fa-power-off"}, {"text": "\uf012", "id": "fa-signal"}, {"text": "\uf013", "id": "fa-cog"}, {"text": "\uf014", "id": "fa-trash-o"}, {"text": "\uf015", "id": "fa-home"}, {"text": "\uf016", "id": "fa-file-o"}, {"text": "\uf017", "id": "fa-clock-o"}, {"text": "\uf018", "id": "fa-road"}, {"text": "\uf019", "id": "fa-download"}, {"text": "\uf01a", "id": "fa-arrow-circle-o-down"}, {"text": "\uf01b", "id": "fa-arrow-circle-o-up"}, {"text": "\uf01c", "id": "fa-inbox"}, {"text": "\uf01d", "id": "fa-play-circle-o"}, {"text": "\uf01e", "id": "fa-repeat"}, {"text": "\uf021", "id": "fa-refresh"}, {"text": "\uf022", "id": "fa-list-alt"}, {"text": "\uf023", "id": "fa-lock"}, {"text": "\uf024", "id": "fa-flag"}, {"text": "\uf025", "id": "fa-headphones"}, {"text": "\uf026", "id": "fa-volume-off"}, {"text": "\uf027", "id": "fa-volume-down"}, {"text": "\uf028", "id": "fa-volume-up"}, {"text": "\uf029", "id": "fa-qrcode"}, {"text": "\uf02a", "id": "fa-barcode"}, {"text": "\uf02b", "id": "fa-tag"}, {"text": "\uf02c", "id": "fa-tags"}, {"text": "\uf02d", "id": "fa-book"}, {"text": "\uf02e", "id": "fa-bookmark"}, {"text": "\uf02f", "id": "fa-print"}, {"text": "\uf030", "id": "fa-camera"}, {"text": "\uf031", "id": "fa-font"}, {"text": "\uf032", "id": "fa-bold"}, {"text": "\uf033", "id": "fa-italic"}, {"text": "\uf034", "id": "fa-text-height"}, {"text": "\uf035", "id": "fa-text-width"}, {"text": "\uf036", "id": "fa-align-left"}, {"text": "\uf037", "id": "fa-align-center"}, {"text": "\uf038", "id": "fa-align-right"}, {"text": "\uf039", "id": "fa-align-justify"}, {"text": "\uf03a", "id": "fa-list"}, {"text": "\uf03b", "id": "fa-outdent"}, {"text": "\uf03c", "id": "fa-indent"}, {"text": "\uf03d", "id": "fa-video-camera"}, {"text": "\uf03e", "id": "fa-picture-o"}, {"text": "\uf040", "id": "fa-pencil"}, {"text": "\uf041", "id": "fa-map-marker"}, {"text": "\uf042", "id": "fa-adjust"}, {"text": "\uf043", "id": "fa-tint"}, {"text": "\uf044", "id": "fa-pencil-square-o"}, {"text": "\uf045", "id": "fa-share-square-o"}, {"text": "\uf046", "id": "fa-check-square-o"}, {"text": "\uf047", "id": "fa-arrows"}, {"text": "\uf048", "id": "fa-step-backward"}, {"text": "\uf049", "id": "fa-fast-backward"}, {"text": "\uf04a", "id": "fa-backward"}, {"text": "\uf04b", "id": "fa-play"}, {"text": "\uf04c", "id": "fa-pause"}, {"text": "\uf04d", "id": "fa-stop"}, {"text": "\uf04e", "id": "fa-forward"}, {"text": "\uf050", "id": "fa-fast-forward"}, {"text": "\uf051", "id": "fa-step-forward"}, {"text": "\uf052", "id": "fa-eject"}, {"text": "\uf053", "id": "fa-chevron-left"}, {"text": "\uf054", "id": "fa-chevron-right"}, {"text": "\uf055", "id": "fa-plus-circle"}, {"text": "\uf056", "id": "fa-minus-circle"}, {"text": "\uf057", "id": "fa-times-circle"}, {"text": "\uf058", "id": "fa-check-circle"}, {"text": "\uf059", "id": "fa-question-circle"}, {"text": "\uf05a", "id": "fa-info-circle"}, {"text": "\uf05b", "id": "fa-crosshairs"}, {"text": "\uf05c", "id": "fa-times-circle-o"}, {"text": "\uf05d", "id": "fa-check-circle-o"}, {"text": "\uf05e", "id": "fa-ban"}, {"text": "\uf060", "id": "fa-arrow-left"}, {"text": "\uf061", "id": "fa-arrow-right"}, {"text": "\uf062", "id": "fa-arrow-up"}, {"text": "\uf063", "id": "fa-arrow-down"}, {"text": "\uf064", "id": "fa-share"}, {"text": "\uf065", "id": "fa-expand"}, {"text": "\uf066", "id": "fa-compress"}, {"text": "\uf067", "id": "fa-plus"}, {"text": "\uf068", "id": "fa-minus"}, {"text": "\uf069", "id": "fa-asterisk"}, {"text": "\uf06a", "id": "fa-exclamation-circle"}, {"text": "\uf06b", "id": "fa-gift"}, {"text": "\uf06c", "id": "fa-leaf"}, {"text": "\uf06d", "id": "fa-fire"}, {"text": "\uf06e", "id": "fa-eye"}, {"text": "\uf070", "id": "fa-eye-slash"}, {"text": "\uf071", "id": "fa-exclamation-triangle"}, {"text": "\uf072", "id": "fa-plane"}, {"text": "\uf073", "id": "fa-calendar"}, {"text": "\uf074", "id": "fa-random"}, {"text": "\uf075", "id": "fa-comment"}, {"text": "\uf076", "id": "fa-magnet"}, {"text": "\uf077", "id": "fa-chevron-up"}, {"text": "\uf078", "id": "fa-chevron-down"}, {"text": "\uf079", "id": "fa-retweet"}, {"text": "\uf07a", "id": "fa-shopping-cart"}, {"text": "\uf07b", "id": "fa-folder"}, {"text": "\uf07c", "id": "fa-folder-open"}, {"text": "\uf07d", "id": "fa-arrows-v"}, {"text": "\uf07e", "id": "fa-arrows-h"}, {"text": "\uf080", "id": "fa-bar-chart-o"}, {"text": "\uf081", "id": "fa-twitter-square"}, {"text": "\uf082", "id": "fa-facebook-square"}, {"text": "\uf083", "id": "fa-camera-retro"}, {"text": "\uf084", "id": "fa-key"}, {"text": "\uf085", "id": "fa-cogs"}, {"text": "\uf086", "id": "fa-comments"}, {"text": "\uf087", "id": "fa-thumbs-o-up"}, {"text": "\uf088", "id": "fa-thumbs-o-down"}, {"text": "\uf089", "id": "fa-star-half"}, {"text": "\uf08a", "id": "fa-heart-o"}, {"text": "\uf08b", "id": "fa-sign-out"}, {"text": "\uf08c", "id": "fa-linkedin-square"}, {"text": "\uf08d", "id": "fa-thumb-tack"}, {"text": "\uf08e", "id": "fa-external-link"}, {"text": "\uf090", "id": "fa-sign-in"}, {"text": "\uf091", "id": "fa-trophy"}, {"text": "\uf092", "id": "fa-github-square"}, {"text": "\uf093", "id": "fa-upload"}, {"text": "\uf094", "id": "fa-lemon-o"}, {"text": "\uf095", "id": "fa-phone"}, {"text": "\uf096", "id": "fa-square-o"}, {"text": "\uf097", "id": "fa-bookmark-o"}, {"text": "\uf098", "id": "fa-phone-square"}, {"text": "\uf099", "id": "fa-twitter"}, {"text": "\uf09a", "id": "fa-facebook"}, {"text": "\uf09b", "id": "fa-github"}, {"text": "\uf09c", "id": "fa-unlock"}, {"text": "\uf09d", "id": "fa-credit-card"}, {"text": "\uf09e", "id": "fa-rss"}, {"text": "\uf0a0", "id": "fa-hdd-o"}, {"text": "\uf0a1", "id": "fa-bullhorn"}, {"text": "\uf0f3", "id": "fa-bell"}, {"text": "\uf0a3", "id": "fa-certificate"}, {"text": "\uf0a4", "id": "fa-hand-o-right"}, {"text": "\uf0a5", "id": "fa-hand-o-left"}, {"text": "\uf0a6", "id": "fa-hand-o-up"}, {"text": "\uf0a7", "id": "fa-hand-o-down"}, {"text": "\uf0a8", "id": "fa-arrow-circle-left"}, {"text": "\uf0a9", "id": "fa-arrow-circle-right"}, {"text": "\uf0aa", "id": "fa-arrow-circle-up"}, {"text": "\uf0ab", "id": "fa-arrow-circle-down"}, {"text": "\uf0ac", "id": "fa-globe"}, {"text": "\uf0ad", "id": "fa-wrench"}, {"text": "\uf0ae", "id": "fa-tasks"}, {"text": "\uf0b0", "id": "fa-filter"}, {"text": "\uf0b1", "id": "fa-briefcase"}, {"text": "\uf0b2", "id": "fa-arrows-alt"}, {"text": "\uf0c0", "id": "fa-users"}, {"text": "\uf0c1", "id": "fa-link"}, {"text": "\uf0c2", "id": "fa-cloud"}, {"text": "\uf0c3", "id": "fa-flask"}, {"text": "\uf0c4", "id": "fa-scissors"}, {"text": "\uf0c5", "id": "fa-files-o"}, {"text": "\uf0c6", "id": "fa-paperclip"}, {"text": "\uf0c7", "id": "fa-floppy-o"}, {"text": "\uf0c8", "id": "fa-square"}, {"text": "\uf0c9", "id": "fa-bars"}, {"text": "\uf0ca", "id": "fa-list-ul"}, {"text": "\uf0cb", "id": "fa-list-ol"}, {"text": "\uf0cc", "id": "fa-strikethrough"}, {"text": "\uf0cd", "id": "fa-underline"}, {"text": "\uf0ce", "id": "fa-table"}, {"text": "\uf0d0", "id": "fa-magic"}, {"text": "\uf0d1", "id": "fa-truck"}, {"text": "\uf0d2", "id": "fa-pinterest"}, {"text": "\uf0d3", "id": "fa-pinterest-square"}, {"text": "\uf0d4", "id": "fa-google-plus-square"}, {"text": "\uf0d5", "id": "fa-google-plus"}, {"text": "\uf0d6", "id": "fa-money"}, {"text": "\uf0d7", "id": "fa-caret-down"}, {"text": "\uf0d8", "id": "fa-caret-up"}, {"text": "\uf0d9", "id": "fa-caret-left"}, {"text": "\uf0da", "id": "fa-caret-right"}, {"text": "\uf0db", "id": "fa-columns"}, {"text": "\uf0dc", "id": "fa-sort"}, {"text": "\uf0dd", "id": "fa-sort-asc"}, {"text": "\uf0de", "id": "fa-sort-desc"}, {"text": "\uf0e0", "id": "fa-envelope"}, {"text": "\uf0e1", "id": "fa-linkedin"}, {"text": "\uf0e2", "id": "fa-undo"}, {"text": "\uf0e3", "id": "fa-gavel"}, {"text": "\uf0e4", "id": "fa-tachometer"}, {"text": "\uf0e5", "id": "fa-comment-o"}, {"text": "\uf0e6", "id": "fa-comments-o"}, {"text": "\uf0e7", "id": "fa-bolt"}, {"text": "\uf0e8", "id": "fa-sitemap"}, {"text": "\uf0e9", "id": "fa-umbrella"}, {"text": "\uf0ea", "id": "fa-clipboard"}, {"text": "\uf0eb", "id": "fa-lightbulb-o"}, {"text": "\uf0ec", "id": "fa-exchange"}, {"text": "\uf0ed", "id": "fa-cloud-download"}, {"text": "\uf0ee", "id": "fa-cloud-upload"}, {"text": "\uf0f0", "id": "fa-user-md"}, {"text": "\uf0f1", "id": "fa-stethoscope"}, {"text": "\uf0f2", "id": "fa-suitcase"}, {"text": "\uf0a2", "id": "fa-bell-o"}, {"text": "\uf0f4", "id": "fa-coffee"}, {"text": "\uf0f5", "id": "fa-cutlery"}, {"text": "\uf0f6", "id": "fa-file-text-o"}, {"text": "\uf0f7", "id": "fa-building-o"}, {"text": "\uf0f8", "id": "fa-hospital-o"}, {"text": "\uf0f9", "id": "fa-ambulance"}, {"text": "\uf0fa", "id": "fa-medkit"}, {"text": "\uf0fb", "id": "fa-fighter-jet"}, {"text": "\uf0fc", "id": "fa-beer"}, {"text": "\uf0fd", "id": "fa-h-square"}, {"text": "\uf0fe", "id": "fa-plus-square"}, {"text": "\uf100", "id": "fa-angle-double-left"}, {"text": "\uf101", "id": "fa-angle-double-right"}, {"text": "\uf102", "id": "fa-angle-double-up"}, {"text": "\uf103", "id": "fa-angle-double-down"}, {"text": "\uf104", "id": "fa-angle-left"}, {"text": "\uf105", "id": "fa-angle-right"}, {"text": "\uf106", "id": "fa-angle-up"}, {"text": "\uf107", "id": "fa-angle-down"}, {"text": "\uf108", "id": "fa-desktop"}, {"text": "\uf109", "id": "fa-laptop"}, {"text": "\uf10a", "id": "fa-tablet"}, {"text": "\uf10b", "id": "fa-mobile"}, {"text": "\uf10c", "id": "fa-circle-o"}, {"text": "\uf10d", "id": "fa-quote-left"}, {"text": "\uf10e", "id": "fa-quote-right"}, {"text": "\uf110", "id": "fa-spinner"}, {"text": "\uf111", "id": "fa-circle"}, {"text": "\uf112", "id": "fa-reply"}, {"text": "\uf113", "id": "fa-github-alt"}, {"text": "\uf114", "id": "fa-folder-o"}, {"text": "\uf115", "id": "fa-folder-open-o"}, {"text": "\uf118", "id": "fa-smile-o"}, {"text": "\uf119", "id": "fa-frown-o"}, {"text": "\uf11a", "id": "fa-meh-o"}, {"text": "\uf11b", "id": "fa-gamepad"}, {"text": "\uf11c", "id": "fa-keyboard-o"}, {"text": "\uf11d", "id": "fa-flag-o"}, {"text": "\uf11e", "id": "fa-flag-checkered"}, {"text": "\uf120", "id": "fa-terminal"}, {"text": "\uf121", "id": "fa-code"}, {"text": "\uf122", "id": "fa-reply-all"}, {"text": "\uf122", "id": "fa-mail-reply-all"}, {"text": "\uf123", "id": "fa-star-half-o"}, {"text": "\uf124", "id": "fa-location-arrow"}, {"text": "\uf125", "id": "fa-crop"}, {"text": "\uf126", "id": "fa-code-fork"}, {"text": "\uf127", "id": "fa-chain-broken"}, {"text": "\uf128", "id": "fa-question"}, {"text": "\uf129", "id": "fa-info"}, {"text": "\uf12a", "id": "fa-exclamation"}, {"text": "\uf12b", "id": "fa-superscript"}, {"text": "\uf12c", "id": "fa-subscript"}, {"text": "\uf12d", "id": "fa-eraser"}, {"text": "\uf12e", "id": "fa-puzzle-piece"}, {"text": "\uf130", "id": "fa-microphone"}, {"text": "\uf131", "id": "fa-microphone-slash"}, {"text": "\uf132", "id": "fa-shield"}, {"text": "\uf133", "id": "fa-calendar-o"}, {"text": "\uf134", "id": "fa-fire-extinguisher"}, {"text": "\uf135", "id": "fa-rocket"}, {"text": "\uf136", "id": "fa-maxcdn"}, {"text": "\uf137", "id": "fa-chevron-circle-left"}, {"text": "\uf138", "id": "fa-chevron-circle-right"}, {"text": "\uf139", "id": "fa-chevron-circle-up"}, {"text": "\uf13a", "id": "fa-chevron-circle-down"}, {"text": "\uf13b", "id": "fa-html5"}, {"text": "\uf13c", "id": "fa-css3"}, {"text": "\uf13d", "id": "fa-anchor"}, {"text": "\uf13e", "id": "fa-unlock-alt"}, {"text": "\uf140", "id": "fa-bullseye"}, {"text": "\uf141", "id": "fa-ellipsis-h"}, {"text": "\uf142", "id": "fa-ellipsis-v"}, {"text": "\uf143", "id": "fa-rss-square"}, {"text": "\uf144", "id": "fa-play-circle"}, {"text": "\uf145", "id": "fa-ticket"}, {"text": "\uf146", "id": "fa-minus-square"}, {"text": "\uf147", "id": "fa-minus-square-o"}, {"text": "\uf148", "id": "fa-level-up"}, {"text": "\uf149", "id": "fa-level-down"}, {"text": "\uf14a", "id": "fa-check-square"}, {"text": "\uf14b", "id": "fa-pencil-square"}, {"text": "\uf14c", "id": "fa-external-link-square"}, {"text": "\uf14d", "id": "fa-share-square"}, {"text": "\uf14e", "id": "fa-compass"}, {"text": "\uf150", "id": "fa-caret-square-o-down"}, {"text": "\uf151", "id": "fa-caret-square-o-up"}, {"text": "\uf152", "id": "fa-caret-square-o-right"}, {"text": "\uf153", "id": "fa-eur"}, {"text": "\uf154", "id": "fa-gbp"}, {"text": "\uf155", "id": "fa-usd"}, {"text": "\uf156", "id": "fa-inr"}, {"text": "\uf157", "id": "fa-jpy"}, {"text": "\uf158", "id": "fa-rub"}, {"text": "\uf159", "id": "fa-krw"}, {"text": "\uf15a", "id": "fa-btc"}, {"text": "\uf15b", "id": "fa-file"}, {"text": "\uf15c", "id": "fa-file-text"}, {"text": "\uf15d", "id": "fa-sort-alpha-asc"}, {"text": "\uf15e", "id": "fa-sort-alpha-desc"}, {"text": "\uf160", "id": "fa-sort-amount-asc"}, {"text": "\uf161", "id": "fa-sort-amount-desc"}, {"text": "\uf162", "id": "fa-sort-numeric-asc"}, {"text": "\uf163", "id": "fa-sort-numeric-desc"}, {"text": "\uf164", "id": "fa-thumbs-up"}, {"text": "\uf165", "id": "fa-thumbs-down"}, {"text": "\uf166", "id": "fa-youtube-square"}, {"text": "\uf167", "id": "fa-youtube"}, {"text": "\uf168", "id": "fa-xing"}, {"text": "\uf169", "id": "fa-xing-square"}, {"text": "\uf16a", "id": "fa-youtube-play"}, {"text": "\uf16b", "id": "fa-dropbox"}, {"text": "\uf16c", "id": "fa-stack-overflow"}, {"text": "\uf16d", "id": "fa-instagram"}, {"text": "\uf16e", "id": "fa-flickr"}, {"text": "\uf170", "id": "fa-adn"}, {"text": "\uf171", "id": "fa-bitbucket"}, {"text": "\uf172", "id": "fa-bitbucket-square"}, {"text": "\uf173", "id": "fa-tumblr"}, {"text": "\uf174", "id": "fa-tumblr-square"}, {"text": "\uf175", "id": "fa-long-arrow-down"}, {"text": "\uf176", "id": "fa-long-arrow-up"}, {"text": "\uf177", "id": "fa-long-arrow-left"}, {"text": "\uf178", "id": "fa-long-arrow-right"}, {"text": "\uf179", "id": "fa-apple"}, {"text": "\uf17a", "id": "fa-windows"}, {"text": "\uf17b", "id": "fa-android"}, {"text": "\uf17c", "id": "fa-linux"}, {"text": "\uf17d", "id": "fa-dribbble"}, {"text": "\uf17e", "id": "fa-skype"}, {"text": "\uf180", "id": "fa-foursquare"}, {"text": "\uf181", "id": "fa-trello"}, {"text": "\uf182", "id": "fa-female"}, {"text": "\uf183", "id": "fa-male"}, {"text": "\uf184", "id": "fa-gittip"}, {"text": "\uf185", "id": "fa-sun-o"}, {"text": "\uf186", "id": "fa-moon-o"}, {"text": "\uf187", "id": "fa-archive"}, {"text": "\uf188", "id": "fa-bug"}, {"text": "\uf189", "id": "fa-vk"}, {"text": "\uf18a", "id": "fa-weibo"}, {"text": "\uf18b", "id": "fa-renren"}, {"text": "\uf18c", "id": "fa-pagelines"}, {"text": "\uf18d", "id": "fa-stack-exchange"}, {"text": "\uf18e", "id": "fa-arrow-circle-o-right"}, {"text": "\uf190", "id": "fa-arrow-circle-o-left"}, {"text": "\uf191", "id": "fa-caret-square-o-left"}, {"text": "\uf192", "id": "fa-dot-circle-o"}, {"text": "\uf193", "id": "fa-wheelchair"}, {"text": "\uf194", "id": "fa-vimeo-square"}, {"text": "\uf195", "id": "fa-try"}, {"text": "\uf196", "id": "fa-plus-square-o"}],
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

            var sizes = ['', 'fa-2x', 'fa-3x', 'fa-4x', 'fa-5x'];
            var classes = this.get_fa_classes();
            var no_sizes = _.difference(classes, sizes).join(' ');
            var selected = false;
            for (var i = sizes.length - 1; i >= 0; i--) {
                var size = sizes[i];

                var $p = $('<span>')
                        .attr('data-size', size)
                        .addClass(size)
                        .addClass(no_sizes);

                if ((size && _.contains(classes, size)) || (size === "" && !selected)) {
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

