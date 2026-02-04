/**
 * Bots admin javascript library
 * Copyright (C) 2021-2026 © Ludovic Watteaux
**/

function get_srcfiler_url() {
    var args = Array.prototype.slice.call(arguments);
    args[args.length - 1] = args[args.length - 1].replaceAll('.', '/') + '.py';
    return url_bots_srcfiler + "/?src=" + args.join('/');
}

function get_grammarsrc_url(editype, messagetype) {
    if (!editype || !messagetype) {
        return false;
    }
    if (!message_types[editype]) {
        return false;
    }
    return get_srcfiler_url('grammars', editype, messagetype)
}


function get_mapping_url() {
    if (!fromeditype.value || !tscript.value) {
        return false;
    }
    if (!tscripts[fromeditype.value]) {
        return false;
    }
    if (tscripts[fromeditype.value].indexOf(tscript.value) == -1) {
        return false;
    }
    return get_srcfiler_url('mappings', fromeditype.value, tscript.value)
}

function get_translate_url() {
    var href = url_bots_translate + "?";
    if (fromeditype.value) {
        href += "fromeditype__exact=" + fromeditype.value + "&";
    }
    if (frommessagetype.value && frommessagetype.value != fromeditype.value) {
        href += "frommessagetype=" + frommessagetype.value + "&";
    }
    if (alt.value) {
        href += "alt=" + alt.value + "&";
    }
    return href;
}

function insertAfter(ref, elem) {
    ref.parentNode.insertBefore(elem, ref.nextSibling);
}


function get_frommessagesrc_url() {
    return get_grammarsrc_url(fromeditype.value, frommessagetype.value);
}

function get_tomessagesrc_url() {
    return get_grammarsrc_url(toeditype.value, tomessagetype.value);
}


function create_span(elem) {
    // Add span and srcfiler link
    var span = document.createElement("span");
    span.id = "span_" + elem.name;
    span.innerHTML = ' <a id="a_' + elem.name + '" href="#" class="icon-py nowrap botsheader" title="View source" onclick="return popup(this)">View</a>';
    insertAfter(elem, span);
}

function create_select(elem) {
    var sel = document.createElement('select');
    sel.setAttribute("id", 'sel_' + elem.name);
    sel.setAttribute("onchange", 'set_' + elem.name + '(this.value);');
    sel.style.display = 'none';
    elem.parentNode.insertBefore(sel, elem);
}


function display_span(field) {
    var span = document.getElementById('span_' + field);
    var a = span.firstElementChild;
    var href = '';
    if (field == 'frommessagetype') {
        href = get_frommessagesrc_url();
    } else if (field == 'tomessagetype') {
        href = get_tomessagesrc_url();
    } else if (field == 'tscript') {
        href = get_mapping_url();
    }
    if (href) {
        a.href = href;
        span.style.display = '';
        return true;
    }
    span.style.display = 'none';
    a.href = "#";
    return false;
}

function display_span_tscript() {
    return display_span('tscript');
}

function display_span_frommessagetype() {
    return display_span('frommessagetype');
}

function display_span_tomessagetype() {
    return display_span('tomessagetype');
}

function set_tscript(script) {
    tscript.value = script;
    display_span_tscript();
}

function set_frommessagetype(msgtype) {
    frommessagetype.value = msgtype;
    display_span_frommessagetype();
    onchange_translateind();
}

function set_tomessagetype(msgtype) {
    tomessagetype.value = msgtype;
    display_span_tomessagetype();
}


function onchange_translateind() {
    /* bots routes translate indicator change */
    if (!translateind) {
        // Not in a route admin change_form
        return;
    }
    var span = document.getElementById('span_translateind');
    var fieldbox_alt = document.querySelector('div.field-alt div.field-alt');
    while (!fieldbox_alt.querySelector('.help')) {
        fieldbox_alt = fieldbox_alt.parentElement;
    }
    if (['0', '1'].indexOf(translateind.value) > -1) {
        var a = span.firstElementChild;
        a.href = get_translate_url();
        a.title = a.getAttribute('data-title') + ': ' + fromeditype.value;
        if (['edifact', 'x12'].indexOf(fromeditype.value) < 0) {
            a.title += ' ' + frommessagetype.value;
        }
        span.style.display = '';
        fieldbox_alt.style.display = '';
    } else {
        span.style.display = 'none';
        fieldbox_alt.style.display = 'none';
        fieldbox_alt.querySelector('input[name="alt"]').value = '';
    }
}


function onchange_editype(editype, onload=false) {
    if (editype == fromeditype) {
        var messagetype = frommessagetype;
        var sel_messagetype = sel_frommessagetype;
    } else if (editype == toeditype) {
        var messagetype = tomessagetype;
        var sel_messagetype = sel_tomessagetype;
    } else {
        return;
    }
    if (!onload) {
        messagetype.value = '';
        sel_messagetype.value = '';
    }
    if (!message_types[editype.value]) {
        messagetype.style.display = '';
        sel_messagetype.style.display = 'none';
    } else {
        sel_messagetype.style.display = '';
        messagetype.style.display = 'none';
        // Clear message types options
        sel_messagetype.innerHTML = "";
        // Add message types options
        message_types[editype.value].forEach(function (msgtype) {
            var name = msgtype;
            if (!msgtype) {
                name = '------ (' + editype.value + ') ------';
            } else {
                name += ' (' + editype.value + ')';
            }
            sel_messagetype.options.add(new Option(name, msgtype));
            if (msgtype == messagetype.value) {
                sel_messagetype.value = msgtype;
            }
        });
        // Set frommessagetype
        if (sel_messagetype.value != messagetype.value) {
            messagetype.value = sel_messagetype.value;
        }
    }
    if (editype == fromeditype) {
        if (!tscript) {
            // for routes admin change_form only
            // Set default frommessagetype for normalised edifact and x12 messages
            if (!onload && ['edifact', 'x12'].indexOf(fromeditype.value) > -1 && message_types[fromeditype.value].indexOf(fromeditype.value) > -1) {
                sel_frommessagetype.value = fromeditype.value;
                frommessagetype.value = fromeditype.value;
            }
            display_span_frommessagetype();
            onchange_translateind();
            return;
        }
        display_span_frommessagetype();
        // Add tscripts options
        sel_tscript.innerHTML = "";
        if (tscripts[editype.value]) {
            tscript.style.display = 'none';
            sel_tscript.style.display = '';
            tscripts[editype.value].forEach(function (script) {
                sel_tscript.options.add(new Option(script, script));
                if (script == tscript.value) {
                    sel_tscript.value = script;
                }
            });
            if (sel_tscript.value != tscript.value) {
                tscript.value = sel_tscript.value;
            }
        } else {
            sel_tscript.style.display = 'none';
            tscript.style.display = '';
            if (!onload) {
                tscript.value = '';
            }
        }
        display_span_tscript();
    } else if (editype == toeditype) {
        display_span_tomessagetype();
    }
}


function onchange_confirmruletype(evt) {
    /* bots confirmrule ruletype change */
    var display_fields = true;
    if (typeof ruletype !== 'undefined') {
        rule_type = ruletype.value;
    } else if (typeof rule_type === 'undefined') {
        console.error('Confirm rule type not found !');
        return;
    }
    if (['', 'all', 'confirmasked'].indexOf(rule_type) > -1) {
        display_fields = false;
    }
    ruletypes.forEach(function (ruletyp) {
        var field_name = ruletyp.replace('route', 'idroute').replace('channel', 'idchannel');
        var field = document.querySelector('.form-row.field-' + field_name);
        if (field) {
            if (!display_fields || (display_fields && ruletyp != rule_type)) {
                field.style.display = 'none';
                if (typeof ruletype !== 'undefined') {
                    field.querySelector('[name="' + field_name + '"]').value = '';
		}
            } else {
                field.style.display = '';
            }
        }
    });
}
