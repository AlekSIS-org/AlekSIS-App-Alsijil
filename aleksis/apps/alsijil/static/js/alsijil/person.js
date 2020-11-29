$(document).ready(function () {
    $("#select_all_container").show();
    $("#select_all_box").change(function (event) {
        if ($(this).is(":checked")) {
            $(document).find('input[name="selected_notes"]').prop({
                indeterminate: false,
                checked: true,
            });
        } else {
            $(document).find('input[name="selected_notes"]').prop({
                indeterminate: false,
                checked: false,
            });
        }
    });

    $('input[name="selected_notes"]').change(function () {
        var checked = $(this).is(":checked");
        var indeterminate = false;
        $(document).find('input[name="selected_notes"]').each(function () {
            if ($(this).is(":checked") !== checked){
                $("#select_all_box").prop({
                    indeterminate: true,
                })
                indeterminate = true;
                return false;
            }
        });
        if (!(indeterminate)) {
            $("#select_all_box").prop({
                indeterminate: false,
                checked: checked,
            });
        }
    });
});