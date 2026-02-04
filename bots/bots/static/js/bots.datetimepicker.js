/*!
 * bots.datetimepicker.js
 *
 * 2019-2023 Ludovic Watteaux
 * https://github.com/xdan/datetimepicker
 */
$(function() {
    $("#id_datefrom").datetimepicker({
        allowBlank:true,
        format: datetime_input_format,
        formatDate: date_input_format,
        formatTime: time_input_format,
        step: 15,
        yearStart: year_start,
        yearEnd: year_end,
        minDate: mindate,
        maxDate: maxdate,
        dayOfWeekStart: 1,
        //highlightedPeriods: [mindate + "," + maxdate + ",Bots period,background-color:#666;color:#fff;"],
        //roundTime: 'round',
        //roundTime: 'floor',
        closeOnDateSelect: true,
        onShow: function(ct) {
            var datefrom = jQuery('#id_datefrom').val();
            var dateuntil = jQuery('#id_dateuntil').val();
            this.setOptions({
                maxDate: dateuntil||maxdate?dateuntil||maxdate:false,
            });
            if (dateuntil.split(' ')[0] == datefrom.split(' ')[0]) {
                this.setOptions({
                    maxTime: dateuntil.split(' ')[1],
                });
            } else {
                this.setOptions({
                    maxTime: '23:59:59',
                });
            };
        },
    });
    $("#id_dateuntil").datetimepicker({
        allowBlank: true,
        format: datetime_input_format,
        formatDate: date_input_format,
        formatTime: time_input_format,
        step: 15,
        yearStart: year_start,
        yearEnd: year_end,
        minDate: mindate,
        maxDate: maxdate,
        dayOfWeekStart: 1,
        closeOnDateSelect: true,
        onShow: function(ct) {
            var datefrom = jQuery('#id_datefrom').val();
            var dateuntil = jQuery('#id_dateuntil').val();
            this.setOptions({
               minDate: datefrom||mindate?datefrom||mindate:false,
            });
            if (dateuntil.split(' ')[0] == datefrom.split(' ')[0]) {
                this.setOptions({
                    minTime: datefrom.split(' ')[1],
                });
            } else {
                this.setOptions({
                    minTime: '00:00:00',
                });
            };
        },
    });
});
