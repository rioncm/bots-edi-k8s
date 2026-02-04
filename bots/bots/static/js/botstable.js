/*!
 * Botstable javascript functions
 *
 * Author: Ludovic Watteaux
 */

/* Botstable actions */
function sorted() {
    sortedby = document.getElementById('id_sortedby').value;
    if (sortedby) {
        th_sorted = document.getElementById('th_' + sortedby);
        if (!th_sorted) {
            return false;
        }
        th_sorted.classList.add("sortedby");
        if (document.getElementById('id_sortedasc').value === 'True') {
            // sort_tag = "▲";
            var cssclass = 'sortedasc';
        } else {
            // sort_tag = "▼";
            var cssclass = 'sorted';
        };
        var div = document.createElement('div');
        div.innerHTML = '<button class="botsheader ico-del-ha ' + cssclass + '" type="submit" name="order" value="" title="Clear sorting"></button>';
        var botsheader = th_sorted.getElementsByClassName("botsheader");
        botsheader[0].parentElement.insertBefore(div.firstElementChild, botsheader[0]);
    }
}


function get_selected(name='sel') {
    return document.querySelectorAll('input[name=' + name + ']:checked');
}


function update_selcount() {
    var selected = get_selected();
    var selcount = document.getElementById('selcount');
    var disabled = true;
    if (selected.length) {
        selcount.innerHTML = selected.length;
        selcount.classList.remove('noafter');
        if (selected.length == selcount.getAttribute("data-total")) {
            // Set checkboxall checked if all lines are selected
            document.querySelector('input[onchange^="checkall"]').checked = true;
        }
    } else {
        selcount.innerHTML = '';
        selcount.classList.add('noafter');
    }
    if (selected.length && document.querySelector('select[name="actions"]').selectedIndex > 0) {
       disabled = false;
    }
    document.querySelector('button[name="action"]').disabled = disabled;
}


function checktrcls(checkbox, cls='filteredfield') {
    var tr = get_parent_tr(checkbox);
    if (checkbox.checked) {
        tr.classList.add(cls);
    } else {
        tr.classList.remove(cls);
        var checkboxall = document.querySelector('input[onchange^="checkall"]');
        if (checkboxall.checked) {
            checkboxall.checked = false;
        }
    }
}

function checktr(checkbox, cls='filteredfield') {
    checktrcls(checkbox, cls);
    update_selcount();
}

function checkall(checkbox, name) {
    var checkboxes = document.getElementsByName(name);
    checkboxes.forEach(function(elem) {
        elem.checked = checkbox.checked;
        // add filteredfield class to parent TR
        checktrcls(elem);
    });
    update_selcount();
}


function confirmaction() {
    var actions = document.getElementById('id_actions');
    if (actions.value) {
        var selected = get_selected();
        if (selected.length) {
            if (['delete', 'confirm'].indexOf(actions.value) == -1) {
                return true;
            }
            var idtas = '';
            selected.forEach(function(sel) {
                idtas += sel.value + ', ';
            });
            return confirm(actions.selectedOptions[0].innerText + ' (' + selected.length + ') : ' + idtas.slice(0, -2));
        }
    }
    return false;
}


/* Botstable queries */
function get_parent(nodename, elem) {
    while (elem.nodeName != nodename) {
        elem = elem.parentNode;
    }
    return elem;
}


function get_parent_tr(elem) {
    return get_parent('TR', elem);
}


function get_parent_td(elem) {
    return get_parent('TD', elem);
}


function get_value(elem) {
    var td = get_parent_td(elem);
    return td.getAttribute('data-value') || td.innerText;
}


function filterfield(elem, id='', prefix='') {
    /* Filter field with value in td of input elem */
    if (id) {
        var value = get_value(elem);
        var field = document.getElementById(id);
    } else {
        var td = get_parent_td(elem);
        var field_name = td.getAttribute('data-field');
        var value = get_value(td);
        if (!field_name) {
            console.error('No elem name to find filter field');
            return false;
        }
        var field = document.querySelector('[name=' + field_name + ']');
    }
    // console.info('Filtering', filter_name, 'with value', value);
    if (field.options) {
        field.value = prefix + value;
    } else if (['datefrom', 'dateuntil'].indexOf(field.name) > -1){
        field.value = value;
    } else {
        field.value += ' ' + prefix + value;
    }
}


function excludefield(elem, id='') {
    return filterfield(elem, id, '-');
}


function clearfield(elem) {
    /* Clear field value of field set in td date-field of input elem or field id string */
    var field;
    if (typeof elem == 'string') {
        field = document.getElementById(elem);
    } else if (elem) {
        field = document.querySelector('[name="' + get_parent_td(elem).getAttribute('data-field') + '"]');
    }
    if (field) {
        field.value = '';
        if (field.onchange) {
            field.onchange();
        }
    }
}


function get_idta(td) {
    /* return idta of td or tr sel.value */
    return td.getAttribute('data-idta') || get_parent_tr(td).querySelector('[name="sel"]').value;
}


function several_values(value) {
    /* return boolean value == '(several values)' */
    return (value.startsWith('('));
}


function insert_li(html, ul) {
    ul.insertAdjacentHTML('afterbegin', '<li>' + html + '</li>');
}


function add_li(html, ul) {
    ul.insertAdjacentHTML('beforeend', '<li>' + html + '</li>');
}


function dropdown(evt) {
    /* Dropdown contextual menu */
    var target = evt.target;
    if (target['done']) {
        /* menu already done */
        return;
    }
    target['done'] = true;
    var td = get_parent_td(target);
    var ul = target.querySelector('ul');
    var value = get_value(td);
    var field_name = td.getAttribute('data-field');

    /* datefrom - dateuntil */
    if (field_name == 'ts') {
        [{'id': 'id_dateuntil', 'text': gettext('Date until'), 'css': 'sortedasc'},
        {'id': 'id_datefrom', 'text': gettext('Date from'), 'css': 'sorted'}].forEach(function(datefield) {
            var field = document.getElementById(datefield['id']);
            var li_date = '<button class="' + datefield['css'] + '" onclick="filterfield(this, \'' + field.id + '\')">' + datefield['text'] + '</button>';
            if (field.value) {
               li_date += '<ul><li><button class="icon-delete" onclick="clearfield(\'' + field.id + '\')" data-after="' + gettext('Clear filter') + '"></button></li></ul>';
            }
            insert_li(li_date, ul);
        });
        return;
    }

    var field = document.querySelector('[name="' + field_name + '"]');
    var field_text = document.querySelector('#th_' + field_name).innerText;
    var title = value;
    var text;
    var filtertitle = ' ' + field_text + ': ' + value;

    /* Add Specific links */
    switch (field.name) {
        case 'status':
        case 'statust':
            filtertitle = ' ' + field_text + ': ' + target.innerText;
            break;
        /* Routes */
        case 'route':
        case 'idroute':
            if (typeof url_bots_routes !== 'undefined') {
                if (!field.querySelector('option[value="' + value + '"]')) {
                    text = field_text.toLowerCase() + ' ' + gettext('not found');
                    title = '';
                    insert_li('<span class="ico-warn" data-after=" ' + text + '" title="' + title + '"></span>', ul);
                    break;
                }
                text = gettext('View Route');
                title = text + ': ' + value;
                insert_li('<a class="ico-idroute" onclick="return view_route(this)" data-after="' + text + '" title="' + title + '"></a>', ul);
            }
            break;

        /* Channels */
        case 'tochannel':
            if (several_values(value)) {break;}
        case 'fromchannel':
        case 'channel':
            if (typeof url_bots_channel !== 'undefined') {
                if (!field.querySelector('option[value="' + value + '"]')) {
                    text = field_text.toLowerCase() + ' ' + gettext('not found');
                    title = '';
                    insert_li('<span class="ico-warn" data-after=" ' + text + '" title="' + title + '"></span>', ul);
                    break;
                }
                var channeltype = target.firstElementChild.getAttribute('data-after');
                text = gettext('View') + ' ' + field_text.toLowerCase();
                title = text + ': ' + value + channeltype;
                text += channeltype;
                insert_li('<a class="ico-' + field.name + '" onclick="return view_channel(this)" data-after="' + text + '" title="' + title + '"></a>', ul);
            }
            break;

        /* Partners */
        case 'topartner':
            if (several_values(value)) {break;}
        case 'frompartner':
        case 'partner':
            if (typeof url_bots_partner !== 'undefined') {
                if (field.querySelector('option[value="' + value + '"]') || inactive_partners.indexOf(value) > -1) {
                    text = gettext('View Partner');
                    title = text + ': ' + value;
                    insert_li('<a class="ico-' + field.name + '" onclick="return view_partner(this)" data-after="' + text + '" title="' + title + '"></a>', ul);
                } else if (typeof url_bots_partner_add !== 'undefined') {
                    text = gettext('Add Partner');
                    title = text + ': ' + value;
                    insert_li('<a class="ico-add-partner" onclick="return add_partner(this)" data-after="' + text + '" title="' + title + '"></a>', ul);
                }
            }
            break;

        /* Grammar src */
        case 'outmessagetype':
            if (several_values(value)) {break;}
        case 'inmessagetype':
        case 'messagetype':
            if (typeof url_bots_srcfiler !== 'undefined') {
                var [editype, messagetype] = get_msgtype(td);
                if (['raw', 'db'].indexOf(editype) == -1) {
                    text = gettext('View grammar');
                    title = text + ': ' + value;
                    insert_li('<a class="icon-py" onmouseenter="view_grammarsrc(this)" onclick="return this.onmouseenter()" data-after="' + text + '" title="' + title + '"></a>', ul);
                }
                if (typeof url_bots_translate !== 'undefined' && !field.querySelector('option[value="' + value + '"]')) {
                    text = gettext('No translate rule for ') + field_text.toLowerCase() + ' ' + value;
                    title = '';
                    insert_li('<span class="ico-warn" data-after=" ' + text + '" title="' + title + '"></span>', ul);
                    break;
                }
            }
        /* translate link */
        case 'outeditype':
        case 'ineditype':
        case 'editype':
        case 'divtext':
            if (typeof url_bots_translate !== 'undefined') {
                text = gettext('View translate(s)');
                title = text + ': ' + value + ' (' + field_text + ')';
                insert_li('<a class="ico-translate" onclick="return view_translate(this)" data-after="' + text + '" title="' + title + '"></a>', ul);
            }
            break;

        /* File Download link */
        case 'outfilename':
            if (several_values(value)) {break;}
        case 'infilename':
        case 'filename':
            if (typeof url_bots_filer !== 'undefined') {
                text = gettext('Download');
                title = text + ' ' + field_text.toLowerCase() + ': ' + value;
                insert_li('<a href="' + url_bots_filer + '/?action=downl&amp;idta=' + get_idta(td) + '" class="ico-save" data-after="' + text + ' ' + field_text.toLowerCase() + '" title="' + title + '"></a>', ul)
            }
            break;

        default:
            break;
    }

    /* Add Clear field */
    if (field.value) {
        text = gettext('Clear filter');
        title = text + ': ' + field_text;
        insert_li('<button class="icon-delete" onclick="return clearfield(this)" data-after="' + text + ' ' + field_text + '" title="' + title + '"></button>', ul);
    }

    /* Skip values not in a select options */
    if (field.options && !field.querySelector('option[value="' + value + '"]')) {
        return;
    }

    /* Add Exclude field */
    if (field.options && !field.querySelector('option[value="-' + value + '"]')) {
        /* Skip exclude values not in a select options */
    } else {
        text = gettext('Exclude');
        insert_li('<button class="ico-no" onclick="return excludefield(this)" data-after="' + text + ' ' + field_text + '" title="' + text + filtertitle + '"></button>', ul);
    }

    /* Add Filter field */
    if (field.value.split(' ').indexOf(value) == -1) {
        text = gettext('Filter');
        insert_li('<button class="icon-filter" onclick="return filterfield(this)" data-after="' + text + ' ' + field_text + '" title="' + text + filtertitle + '"></button>', ul);
    }
}


function fieldchange(field) {
    /* Add and remove clear field in selectform  */
    var tr = get_parent_tr(field);
    var td_clear = tr.querySelector('td.middle');
    var filteredfield;
    if (['checkbox', 'radio'].indexOf(field.type) > -1) {
        if (field.checked) {
            filteredfield = true;
        }
    } else if (field.value) {
        if (!tr.classList.contains('filteredfield')) {
            td_clear.innerHTML = '<button onclick="clearfield(\'' + field.id  + '\');return false;" type="button" title="'+ gettext('Clear filter') + ': ' + field.labels[0].innerHTML + '" class="botsheader bt-del">&nbsp;</button>';
        }
        filteredfield = true;
    }
    if (filteredfield) {
        tr.classList.add('filteredfield');
    } else {
        tr.classList.remove('filteredfield');
        td_clear.innerHTML = '';
    }
}


function filteredtds() {
    /* Add filteredfield css class to #botstable tbody tr td */
    var filteredcols = [];
    document.querySelectorAll('#botstable thead th.filteredfield').forEach(function(th) {
       filteredcols.push(th.cellIndex);
    });
    if (filteredcols.length) {
        document.querySelectorAll("#botstable tbody tr:not(.errortext)").forEach(function(tr) {
            var tds = tr.querySelectorAll('td');
            filteredcols.forEach(function(col) {
                if (tds[col]) {
                    tds[col].classList.add('filteredfield');
                }
            });
        });
    }
    /* errortext */
    var errortext = document.querySelector("#id_errortext");
    if (errortext && errortext.value) {
        document.querySelectorAll("#botstable tbody tr.errortext").forEach(function(tr) {
            tr.querySelector("td .errortext").parentElement.classList.add("filteredfield");
        });
    }
}
