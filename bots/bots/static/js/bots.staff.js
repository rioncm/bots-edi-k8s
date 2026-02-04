/*!
 * Bots staff & admin javascript functions
 *
 * Author: Ludovic Watteaux
 */

function view_partner(elem, width='60%', height='80%', args='?_popup') {
    if (typeof url_bots_partner == 'undefined') {
        return false;
    }
    if (!elem.href) {
        var idpartner = get_value(elem);
        elem.href = url_bots_partner + idpartner + '/change/' + args;
    }
    return popup(elem, width, height);
}


function add_partner(elem, width='60%', height='80%', args='&_popup') {
    if (typeof url_bots_partner_add == 'undefined') {
        return false;
    }
    if (!elem.href) {
        var idpartner = get_value(elem);
        elem.href = url_bots_partner_add + '?idpartner=' + idpartner + '&name=' + idpartner + args;
    }
    return popup(elem, width, height);
}


function view_channel(elem, width='55%', height='80%', args='?_popup') {
    if (typeof url_bots_channel == 'undefined') {
        return false;
    }
    if (!elem.href) {
        var idchannel = get_value(elem);
        elem.href = url_bots_channel + idchannel + '/change/' + args;
    }
    return popup(elem, width, height);
}


function view_route(elem, args='') {
    if (typeof url_bots_routes == 'undefined') {
        return false;
    }
    if (!elem.href) {
        var idroute = get_value(elem);
        elem.href = url_bots_routes + '?idroute=' + idroute + args;
        elem.target = '_blank';
    }
}


function view_translate(elem, args='') {
    if (elem.href) {
        return;
    }
    if (typeof url_bots_translate == 'undefined') {
        return false;
    }
    elem.href = url_bots_translate;
    elem.target = '_blank';
    var td = get_parent_td(elem);
    var tr = td.parentNode;
    if (['in', 'ou'].indexOf(td.getAttribute('data-field').substring(0, 2)) == -1) {
        var editype = tr.querySelector('[data-field="editype"]');
        var messagetype = tr.querySelector('[data-field="messagetype"]');
        var outeditype = editype;
        var outmessagetype = messagetype;
        var td_status = tr.querySelector('[data-field="status"]');
        if (td_status) {
            var ta_status = Number(get_value(td_status));
            if (ta_status < 330) {
                var ineditype = editype;
                var inmessagetype = messagetype;
                outeditype = null;
                outmessagetype = null;
            }
        }
    } else if (td.getAttribute('data-field').substring(0, 2) == 'in'|| td.getAttribute('data-field') == 'divtext') {
        var ineditype = tr.querySelector("[data-field=ineditype]");
        var inmessagetype = tr.querySelector('[data-field="inmessagetype"]');
    } else if (td.getAttribute('data-field').substring(0, 3) == 'out') {
        var outeditype = tr.querySelector('[data-field="outeditype"]');
        var outmessagetype = tr.querySelector('[data-field="outmessagetype"]');
    }
    if (outeditype) {
        if (outeditype.innerText[0] != '(') {
            elem.href += '?toeditype__exact=' + outeditype.innerText;
        }
        if (td.getAttribute('data-field').indexOf('messagetype') > -1 && outmessagetype.innerText[0] != '(') {
            elem.href += '&tomessagetype=' + outmessagetype.innerText;
        }
        return;
    }
    var tscript = tr.querySelector('[data-field="divtext"]');
    if (ineditype) {
        // fromeditype (ineditype)
        elem.href += '?fromeditype__exact=' + ineditype.innerText;
        // frommessagetype (inmessagetype)
        if (td != ineditype) {
            elem.href += '&frommessagetype=' + inmessagetype.innerText;
        }
    } else if (td == tscript && tscript.innerText[0] != '(') {
        elem.href += '?tscript=' + tscript.innerText;
    }
    elem.href += args
}


function get_msgtype(elem) {
    var td = get_parent_td(elem);
    var tr = td.parentNode;
    var inorout = '';
    if (td.getAttribute('data-field').substring(0, 2) == 'in') {
        var inorout = 'in';
    } else if (td.getAttribute('data-field').substring(0, 3) == 'out') {
        var inorout = 'out';
    }
    var editype = tr.querySelector('[data-field="' + inorout + 'editype"]');
    var messagetype = tr.querySelector('[data-field="' + inorout + 'messagetype"]');
    if (editype) {
        editype = editype.innerText;
    }
    if (messagetype) {
        messagetype = messagetype.innerText;
    }
    return [editype, messagetype];
}


function view_grammarsrc(elem) {
    /* Used by botstable/dropdown/messagetype */
    if (typeof url_bots_srcfiler == 'undefined') {
        return false;
    }
    if (elem.href) {
        return view_src(elem);
    }
    var [editype, messagetype] = get_msgtype(elem);
    if (editype && messagetype) {
        if (['raw', 'db'].indexOf(editype) == -1) {
            elem.title = elem.getAttribute('data-after');
            return view_src(elem, 'grammars', editype, messagetype);
        }
    }
    var err = 'Message type unknown: ' + editype + ' (' + messagetype + ')';
    elem.title = err;
    console.error(err);
    elem.removeAttribute('onclick');
    elem.removeAttribute('onmouseenter');
}


function view_src(elem) {
    /* Set href of input link element with bots source filer url and arguments:
     * args[0]: link element
     * args[1]: ('grammars', 'mappings', ...)
     * args[2]: editype: ('xml', 'x12', 'edifact', ...)
     * args[3]: messagetype: ('ORDERD96A', '850005010', 'UBL21.Invoice', ...)
     */
    if (typeof url_bots_srcfiler == 'undefined') {
        return false;
    }
    if (!elem.href) {
        var args = Array.prototype.slice.call(arguments, 1);
        if (args.length < 2) {
            var err = 'Not enought arguments to format href.';
            alert(err);
            console.error(err);
            return false;
        }
        args[args.length -1] = args[args.length -1].replaceAll('.', '/') + '.py';
        elem.title += ': ' + args.join('/');
        elem.href = url_bots_srcfiler + '/?src=' + args.join('/');
        elem.target = elem.href;
    }
    if (event.type == 'click') {
        if (!window.menubar.visible && elem.getAttribute('onclick').indexOf('popup(') == -1) {
            return popup(elem);
        }
    }
    return elem.href;
}
