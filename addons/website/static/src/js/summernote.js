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

    dom.hasContentAfter = function (node) {
        var next;
        while (node.nextSibling) {
            next = node.nextSibling;
            if (next.tagName || next.textContent.match(/\S/)) return next;
            node = next;
        }
    };
    dom.hasContentBefore = function (node) {
        var prev;
        while (node.previousSibling) {
            prev = node.previousSibling;
            if (prev.tagName || prev.textContent.match(/\S/)) return prev;
            node = prev;
        }
    };
    dom.ancestorHaveNextSibling = function (node, pred) {
        pred = pred || dom.hasContentAfter;
        while (!node.nextSibling || !pred(node)) { node = node.parentNode; }
        return node;
    };
    dom.ancestorHavePreviousSibling = function (node, pred) {
        pred = pred || dom.hasContentBefore;
        while (!node.previousSibling || !pred(node)) { node = node.parentNode; }
        return node;
    };
    dom.lastChild = function (node) {
        while (node.lastChild) { node = node.lastChild; }
        return node;
    };
    dom.firstChild = function (node) {
        while (node.firstChild) { node = node.firstChild; }
        return node;
    };
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
            if (prev.childNodes.length && !prev.textContent.match(/\S/) && prev.firstElementChild && prev.firstElementChild.tagName === "BR") {
                prev.removeChild(prev.firstElementChild);
            }
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
    dom.removeBetween = function (sc, so, ec, eo) {
        var ancestor = dom.commonAncestor(sc, ec);

        if (ancestor.tagName) {

            var ancestor_sc = sc;
            var ancestor_ec = ec;
            while (ancestor !== ancestor_sc.parentNode) { ancestor_sc = ancestor_sc.parentNode; }
            while (ancestor !== ancestor_ec.parentNode) { ancestor_ec = ancestor_ec.parentNode; }

            var begin = dom.splitTree(ancestor_sc, sc, so);
            var last = dom.splitTree(ancestor_ec, ec, eo).previousSibling;
            var nodes = dom.listBetween(begin, last);
            sc = dom.lastChild(begin.previousSibling);
            so = sc.textContent.length;
            
            for (var i=0; i<nodes.length; i++) {
                nodes[i].parentNode.removeChild(nodes[i]);
            }

            var haveNextSibling = dom.ancestorHaveNextSibling(sc);
            var next = dom.hasContentAfter(haveNextSibling);
            if (next && haveNextSibling.tagName === next.tagName) {
                dom.doMerge(haveNextSibling, next);
            }

        } else {

            var text = ancestor.textContent;
            ancestor.textContent = text.slice(0, so) + text.slice(eo, Infinity);

        }
        return {
            node: sc,
            offset: so
        };
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
    range.WrappedRange.prototype.clean = function (mergeFilter) {
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
    range.WrappedRange.prototype.remove = function (mergeFilter) {
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
    
    settings.options.merge = "h1 h2 h3 h4 h5 h6 p b bold i u code sup strong small li a ul ol font".split(" ");
    settings.options.split = "h1 h2 h3 h4 h5 h6 p b bold i u code sup strong small li a font".split(" ");
    settings.options.deleteEmpty = "h1 h2 h3 h4 h5 h6 p b bold i u code sup strong small li a ul ol font span".split(" ");
    settings.options.forbiddenWrite = ".media_iframe_video .fa img".split(" ");

    eventHandler.editor.tab = function ($editable, options, outdent) {
        var r = range.create();
        var outdent = outdent || false;

        if (r.isCollapsed()) {
            if (r.isOnCell()) {
                var td = dom.ancestor(r.sc, dom.isCell);
                if (!outdent && !td.nextElementSibling && !td.parentNode.nextElementSibling) {
                    range.create(td.lastChild, td.lastChild.textContent.length, td.lastChild, td.lastChild.textContent.length).select();
                    eventHandler.editor.enter($editable, options);
                } else if (outdent && !td.previousElementSibling && !$(td.parentNode).text().match(/\S/)) {
                    eventHandler.editor.backspace($editable, options);
                } else {
                    $editable.data('NoteHistory').splitNext(); // for odoo
                    this.table.tab(r, outdent);
                }
                return false;
            }

            if (r.so && r.sc.textContent.slice(0, r.so).match(/\S/)) {
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
        return false;
    };
    eventHandler.editor.untab = function ($editable, options) {
        return this.tab($editable, options, true);
    };
    eventHandler.editor.enter = function ($editable, options) {
        $editable.data('NoteHistory').recordUndo($editable, 'enter');

        var r = range.create();
        if (!r.isCollapsed()) {
            r = r.deleteContents().select();
        }

        // table: add a tr
        var td = dom.ancestor(r.sc, dom.isCell);
        if (td && (r.sc === td || r.sc === td.lastChild || (td.lastChild.tagName === "BR" && r.sc === td.lastChild.previousSibling)) && r.so === r.sc.textContent.length && r.isOnCell() && !td.nextElementSibling) {
            var $node = $(td.parentNode);
            var $clone = $node.clone();
            $clone.children().html(dom.blank);
            $node.after($clone);
            var node = $clone[0].firstElementChild || $clone[0];
            range.create(node, 0, node, 0).select();
            return false;
        }

        var node = !r.sc.tagName ? r.sc.parentNode : r.sc;
        var last = node;
        while (settings.options.split.indexOf(node.tagName.toLowerCase()) !== -1) {
            last = node;
            node = node.parentNode;
        }

        if (last === node) {
            node = r.insertNode($('<br/>')[0]).nextSibling;
        } else if (last === r.sc) {
            var $node = $(last);
            var $clone = $node.clone().text("");
            $node.after($clone);
            node = $clone[0].firstElementChild || $clone[0];
        } else if (r.so) {
            node = dom.splitTree(last, r.sc, r.so);
        } else if (!r.so && r.isOnList() && !r.sc.textContent.length && !dom.ancestor(r.sc, function (node) { return node.tagName === 'LI'; }).nextElementSibling) {
            // double enter on the end of a list = new line out of the list
            node = $('<p><br/></p>').insertAfter(dom.ancestor(r.sc, dom.isList))[0];
        }  else {
            var totalOffset = dom.makeOffsetPath(last, r.sc).reduce(function(pv, cv) { return pv + cv; }, 0);
            node = dom.splitTree(last, r.sc, r.so);
            if (!totalOffset) {
                var prev = dom.hasContentBefore(dom.ancestorHavePreviousSibling(r.sc));
                $(dom.lastChild(prev)).html('<br/>');
            }
        }

        range.create(dom.firstChild(node),0,dom.firstChild(node),0).select();
        return false;
    };
    eventHandler.editor.visible = function ($editable, options) {
        $editable.data('NoteHistory').recordUndo($editable, "visible");

        var r = range.create();
        if (!r.isCollapsed()) {
            r = r.deleteContents().select();
        }

        var node = r.sc;
        var needChange = false;
        while (node.parentNode) {
            if ($(node).is(settings.options.forbiddenWrite.join(","))) {
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
        return false;
    };

    function summernote_keydown_clean (field) {
        setTimeout(function () {
            var r = range.create();
            if (!r) return;
            var node = r[field];
            while (!node.tagName) {node = node.parentNode;}
            node = node.parentNode;
            var data = dom.merge(node, r.sc, r.so, r.ec, r.eo, null, true);
            data = dom.removeSpace(node, data.sc, data.so, data.sc, data.so);

            range.create(data.sc, data.so, data.sc, data.so).select();
        },0);
    }
    eventHandler.editor.delete = function ($editable, options) {
        $editable.data('NoteHistory').recordUndo($editable, "delete");
        
        var r = range.create();
        var isCollapsed = r.isCollapsed();
        if (!isCollapsed) {
            r = r.deleteContents().select();
            return;
        }

        var node = r.ec;
        while (!node.nextSibling && !node.previousSibling) {node = node.parentNode;}
        
        var content = r.ec.textContent.replace(/\s+$/, '');
        var temp;

        // media
        if (r.sc===r.ec && dom.isImg(node)) {
            var parent;
            var index;
            while (dom.isImg(node)) {
                parent = node.parentNode;
                index = dom.makeOffsetPath(parent, node)[0];
                if (index>0)
                range.create(node.previousSibling,0,node.previousSibling,0).select();
                parent.removeChild(node);
                node = parent;
            }
        }
        // empty tag
        else if (r.sc===r.ec && !content.length && node.nextSibling && r.sc.tagName && settings.options.deleteEmpty.indexOf(r.sc.tagName.toLowerCase()) !== -1) {
            var next = node.nextSibling;
            while (next.tagName && next.firstChild) {next = next.firstChild;}
            node.parentNode.removeChild(node);
            range.create(next, 0, next, 0).select();
        }
        // normal feature if same tag and not the end
        else if (r.sc===r.ec && r.eo<content.length && content.length) return true;
        // merge with the next text node
        else if (!r.ec.tagName && r.ec.nextSibling && (!r.sc.nextSibling.tagName || r.sc.nextSibling.tagName === "BR")) return true;
        // jump to next node for delete
        else if ((temp = dom.ancestorHaveNextSibling(r.sc)) && temp.tagName  !== ((temp = dom.hasContentAfter(temp) || {}).tagName)) {
            r = range.create(temp, 0, temp, 0).select();
            return this.delete($editable, options);
        }
        //merge with the next block
        else if (r.isCollapsed() && r.eo>=content.length && settings.options.merge.indexOf(r.ec.parentNode.tagName.toLowerCase()) !== -1) {

            summernote_keydown_clean("ec");
            var next = r.ec.parentNode.nextElementSibling;
            var style = window.getComputedStyle(next);

            if (next && (r.sc.parentNode.tagName === next.tagName || (style.display !== "block" && style.display !== "table") || !parseInt(style.height))) {

                dom.doMerge(r.sc.parentNode, next);
                range.create(r.sc, r.so, r.sc, r.so).select();

            } else {
                var check = false;
                var node = r.sc.tagName ? dom.firstChild(r.sc) : r.sc;
                var nodes = [];

                do {
                    nodes.push(node);
                    node = node.parentNode;
                    if (node.nextElementSibling) {
                        if (node.nextElementSibling.tagName === node.tagName) {
                            nodes.push(node);
                        }
                        break;
                    }
                }  while (node && settings.options.merge.indexOf(node.tagName.toLowerCase()) !== -1);

                var merge = false;
                while (nodes.length) {
                    node = nodes.pop();
                    if (node && node.nextElementSibling && node.nextElementSibling.tagName === node.tagName) {
                        dom.doMerge(node, node.nextElementSibling);
                        merge = true;
                    }
                }
                range.create(r.ec, r.ec.textContent.length, r.ec, r.ec.textContent.length).select();

                if (!merge) {
                    var next = node.tagName ? node.nextElementSibling : node.parentNode.nextElementSibling;
                    while (next.firstElementChild) {
                        next = next.firstElementChild;
                    }
                    range.create(next.firstChild || next, 0, next.firstChild || next, 0).select();
                }
            }
        }
        clean_dom_onkeydown();
        return false;
    };
    eventHandler.editor.backspace = function ($editable, options) {
        $editable.data('NoteHistory').recordUndo($editable, "backspace");
        var temp;
        var r = range.create();
        if (!r.isCollapsed()) {
            r = r.deleteContents().select();
            return;
        }

        var node = r.sc;
        while (!node.nextSibling && !node.previousSibling) {node = node.parentNode;}

        var content = r.ec.textContent.replace(/\s+$/, '');

        // empty tag
        if (r.sc===r.ec && !content.length  && node.previousSibling && r.sc.tagName && settings.options.deleteEmpty.indexOf(r.sc.tagName.toLowerCase()) !== -1) {
            var next = node.previousSibling;
            while (next.tagName && next.lastChild) {next = next.lastChild;}
            node.parentNode.removeChild(node);
            range.create(next, next.textContent.length, next, next.textContent.length).select();
        }
        // table tr td
        else if (r.sc===r.ec && r.isOnCell() && !r.so && (r.sc === (temp = dom.ancestor(r.sc, dom.isCell)) || r.sc === temp.firstChild)) {
            if (temp.previousElementSibling) {
                var td = temp.previousElementSibling;
                node = td.lastChild || td;
                range.create(node, node.textContent.length, node, node.textContent.length).select();
            } else {
                var tr = temp.parentNode;
                var prevTr = tr.previousElementSibling;
                if (!$(temp.parentNode).text().match(/\S/)) {
                    if (prevTr) {
                        tr.parentNode.removeChild(tr);
                        node = (prevTr.lastElementChild.lastChild && prevTr.lastElementChild.lastChild.tagName ? prevTr.lastElementChild.lastChild.previousSibling : prevTr.lastElementChild.lastChild) || prevTr.lastElementChild;
                        range.create(node, node.textContent.length, node, node.textContent.length).select();
                    }
                } else {
                    node = prevTr.lastElementChild.lastChild || prevTr.lastElementChild;
                    range.create(node, node.textContent.length, node, node.textContent.length).select();
                }
            }
        }
        // normal feature if same tag and not the begin
        else if (r.sc===r.ec && r.so || r.eo) return true;
        // merge with the previous text node
        else if (!r.ec.tagName && r.ec.previousSibling && (!r.sc.previousSibling.tagName || r.sc.previousSibling.tagName === "BR")) return true;
        // jump to previous node for delete
        else if ((temp = dom.ancestorHavePreviousSibling(r.sc)) && temp.tagName !== ((temp = dom.hasContentBefore(temp) || {}).tagName)) {
            temp = dom.lastChild(temp);
            r = range.create(temp, temp.textContent.length, temp, temp.textContent.length).select();
            return this.backspace($editable, options);
        }
        //merge with the previous block
        else if (r.isCollapsed() && !r.eo && settings.options.merge.indexOf(r.sc.parentNode.tagName.toLowerCase()) !== -1) {

            summernote_keydown_clean("sc");
            var prev = r.sc.parentNode.previousElementSibling;
            var style = window.getComputedStyle(prev);

            if (prev && (r.sc.parentNode.tagName === prev.tagName || style.display !== "block" || !parseInt(style.height))) {

                dom.doMerge(prev, r.sc.parentNode);
                range.create(r.sc, 0, r.sc, 0).select();

            } else {
                var check = false;
                var node = r.sc.tagName ? dom.firstChild(r.sc) : r.sc;
                var nodes = [];

                do {
                    nodes.push(node);
                    node = node.parentNode;
                    if (node.previousElementSibling) {
                        if (node.previousElementSibling.tagName === node.tagName) {
                            nodes.push(node);
                        }
                        break;
                    }
                }  while (node && settings.options.merge.indexOf(node.tagName.toLowerCase()) !== -1);

                while (nodes.length) {
                    node = nodes.pop();
                    if (node && node.previousElementSibling && node.previousElementSibling.tagName === node.tagName) {
                        dom.doMerge(node.previousElementSibling, node);
                    }
                }
                range.create(node, 0, node, 0).select();
            }
        }

        clean_dom_onkeydown();
        return false;
    };

    //////////////////////////////////////////////////////////////////////////////////////////////////////////
    /* add list command (create a uggly dom for chrome) */

    function isFormatNode(node) {
        return node.tagName && settings.options.styleTags.indexOf(node.tagName.toLowerCase()) !== -1;
    }

    eventHandler.editor.insertUnorderedList = function ($editable, sorted) {
        $editable.data('NoteHistory').recordUndo($editable);

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
        return false;
    };
    eventHandler.editor.insertOrderedList = function ($editable) {
        return this.insertUnorderedList($editable, true);
    };
    eventHandler.editor.indent = function ($editable, outdent) {
        $editable.data('NoteHistory').recordUndo($editable);
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
                        var num = (b ? +b : 0) + (outdent ? -1 : 1);
                        if (num <= 0) return '';
                        return 'indent' + (num > 6 ? 6 : num);
                    });

                if (!ul.className.length) {
                    ul.removeAttribute("class");
                }
            } else if (!outdent) {
                ul.className += ' indent1';
            } else {
                console.log(ul, li);
                dom.splitTree(ul, li, 0);
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
        return false;
    };
    eventHandler.editor.outdent = function ($editable) {
        return this.indent($editable, true);
    };

    //////////////////////////////////////////////////////////////////////////////////////////////////////////
    
    function createFontNode() {
        var r = range.create();
        if (r.sc !== r.ec || r.so || r.eo !== r.sc.textContent.length) {
            document.execCommand('foreColor', false, "red");
            r = range.create();
        }
        return $(dom.listBetween(r.sc, r.ec)).add(r.sc.tagName ? r.sc : r.sc.parentNode).add(r.sc.tagName ? r.sc : r.sc.parentNode).filter('font').removeAttr("color").get();
    }
    var color = {
        foreColor: function (nodes, sObjColor) {
            for (var i=0; i<nodes.length; i++) {
                var node = nodes[i];
                node.className = (node.className || '').replace(/\s*text-[^\s]+/, '');
                node.removeAttribute('color');
                node.style.color = '';
                if (!sObjColor.indexOf('text-')) {
                    node.className = (node.className || '').replace(/\s*text-[^\s]+\s*/, '') + ' ' + sObjColor;
                } else {
                    node.setAttribute('color', sObjColor);
                }
            }
        },
        backColor: function (nodes, sObjColor) {
            for (var i=0; i<nodes.length; i++) {
                var node = nodes[i];
                node.className = (node.className || '').replace(/\s*bg-[^\s]+/, '');
                node.style.backgroundColor = "";
                if (!sObjColor.indexOf('bg-')) {
                    node.className = (node.className || '').replace(/\s*bg-[^\s]+\s*/, '') + ' ' + sObjColor;
                } else {
                    node.style.backgroundColor = sObjColor;
                }
            }
        }
    };
    eventHandler.editor.foreColor = function ($editable, sObjColor) {
        var nodes = createFontNode();
        color.foreColor(nodes, sObjColor);
        return false;
    };
    eventHandler.editor.backColor = function ($editable, sObjColor) {
        var nodes = createFontNode();
        color.backColor(nodes, sObjColor);
        return false;
    };
    eventHandler.editor.removeFormat = function ($editable) {
        var node = range.create().sc.parentNode;
        document.execCommand('removeFormat');
        document.execCommand('removeFormat');
        var r = range.create();
        r = dom.merge(node, r.sc, r.so, r.ec, r.eo, null, true);
        range.create(r.sc, r.so, r.ec, r.eo).select();
        return false;
    };
    var fn_boutton_updateRecentColor = eventHandler.toolbar.button.updateRecentColor;
    eventHandler.toolbar.button.updateRecentColor = function (elBtn, sEvent, sValue) {
        fn_boutton_updateRecentColor.call(this, elBtn, sEvent, sValue);
        color[sEvent]($(elBtn).closest('.note-color').find('.note-recent-color i')[0], sValue);
        return false;
    };

    //////////////////////////////////////////////////////////////////////////////////////////////////////////
    /* table */
    
    function summernote_table_scroll (event) {
        var r = range.create();
        if (r && r.isOnCell()) {
            $('.o_table_handler').remove();
        }
    }
    function summernote_table_update (oStyle) {
        if (!range.create().isOnCell()) {
            $('.o_table_handler').remove();
            return;
        }
        var table = dom.ancestor(oStyle.range.sc, dom.isTable);
        var $editable = $(table).closest('.o_editable');

        $('.o_table_handler').remove();

        var $dels = $();
        var $adds = $();
        var $tds = $('tr:first', table).children();
        $tds.each(function () {
            var $td = $(this);
            var pos = $td.offset();

            var $del = $('<span class="o_table_handler fa fa-minus-square"/>').appendTo('body');
            $del.data('td', this);
            $dels = $dels.add($del);
            $del.css({
                left: ((pos.left + $td.outerWidth()/2)-6) + "px",
                top: (pos.top-6) + "px"
            });

            var $add = $('<span class="o_table_handler fa fa-plus-square"/>').appendTo('body');
            $add.data('td', this);
            $adds = $adds.add($add);
            $add.css({
                left: (pos.left-6) + "px",
                top: (pos.top-6) + "px"
            });
        });

        var $last = $tds.last();
        var pos = $last.offset();
        var $add = $('<span class="o_table_handler fa fa-plus-square"/>').appendTo('body');
        $adds = $adds.add($add);
        $add.css({
            left: (pos.left+$last.outerWidth()-6) + "px",
            top: (pos.top-6) + "px"
        });

        var $table = $(table);
        $dels.on('mousedown', function (event) {
            var td = $(this).data('td');
            $editable.data('NoteHistory').recordUndo($editable);

            var newTd;
            if ($(td).siblings().length) {
                var eq = $(td).index();
                $table.find('tr').each(function () {
                    $('td:eq('+eq+')', this).remove();
                });
                newTd = $table.find('tr:first td:eq('+eq+'), tr:first td:last').first();
            } else {
                var r = range.create($table[0], 0, $table[0], 1);
                r.select();
                r.deleteContents();
                $('.o_table_handler').remove();
                r = range.create();
                range.create(r.sc, r.so, r.sc, r.so).select();
                $(r.sc).trigger('mouseup');
                return;
            }

            $('.o_table_handler').remove();
            range.create(newTd[0], 0, newTd[0], 0).select();
            newTd.trigger('mouseup');
        });
        $adds.on('mousedown', function (event) {
            var td = $(this).data('td');
            $editable.data('NoteHistory').recordUndo($editable);

            var newTd;
            if (td) {
                var eq = $(td).index();
                $table.find('tr').each(function () {
                    $('td:eq('+eq+')', this).before('<td>'+dom.blank+'</td>');
                });
                newTd = $table.find('tr:first td:eq('+eq+')');
            } else {
                $table.find('tr').each(function () {
                    $(this).append('<td>'+dom.blank+'</td>');
                });
                newTd = $table.find('tr:first td:last');
            }

            $('.o_table_handler').remove();
            range.create(newTd[0], 0, newTd[0], 0).select();
            newTd.trigger('mouseup');
        });

        $dels.css({
            'position': 'absolute',
            'cursor': 'pointer',
            'background-color': '#fff',
            'color': '#ff0000'
        });
        $adds.css({
            'position': 'absolute',
            'cursor': 'pointer',
            'background-color': '#fff',
            'color': '#00ff00'
        });
    }
    var fn_popover_update = eventHandler.popover.update;
    eventHandler.popover.update = function ($popover, oStyle, isAirMode) {
        fn_popover_update.call(this, $popover, oStyle, isAirMode);
        summernote_table_update(oStyle);
    };

    //////////////////////////////////////////////////////////////////////////////////////////////////////////

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
        $editable = $editable.is('[contenteditable]') ? $editable : $editable.find('[contenteditable]');
        $editable.data('NoteHistory').recordUndo($editable);

        event.preventDefault();
        var r = range.create();
        if (!r.isCollapsed()) {
            r = r.deleteContents().select();
        }
        dom.pasteText(r.sc, r.so, clipboardData.getData("text/plain"));
        return false;
    }

    var fn_attach = eventHandler.attach;
    eventHandler.attach = function (oLayoutInfo, options) {
        var $editable = oLayoutInfo.editor.hasClass('note-editable') ? oLayoutInfo.editor : oLayoutInfo.editor.find('.note-editable');
        fn_attach.call(this, oLayoutInfo, options);
        oLayoutInfo.editor.on("paste", summernote_paste);
        $editable.on("scroll", summernote_table_scroll);
    };
    var fn_dettach = eventHandler.dettach;
    eventHandler.dettach = function (oLayoutInfo, options) {
        var $editable = oLayoutInfo.editor.hasClass('note-editable') ? oLayoutInfo.editor : oLayoutInfo.editor.find('.note-editable');
        fn_dettach.call(this, oLayoutInfo, options);
        oLayoutInfo.editor.off("paste", summernote_paste);
        $editable.off("scroll", summernote_table_scroll);
    };

})();
