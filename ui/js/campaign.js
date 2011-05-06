// Add calculator widget to the contribution_amount field.
var Campaign = {
    init: function() {
        var input = document.getElementById('id_contribution_amount');
		if (input) {
			Campaign.addCalculator(input);
			Campaign.calculate();
		}
    },
    addCalculator: function(inp) {
        var calculator_span = document.createElement('div');
		calculator_span.setAttribute('id', 'campaignCalculator');
        inp.parentNode.insertBefore(calculator_span, inp.nextSibling);
        addEvent(inp, 'keyup', Campaign.calculate);
		var max_num = document.getElementById('id_max_contributions');
		addEvent(max_num, 'keyup', Campaign.calculate);
    },
    calculate: function() {
		var calculated = document.getElementById('campaignCalculator');
        var amount = document.getElementById('id_contribution_amount').value;
        var max_num = document.getElementById('id_max_contributions').value;
		var target_amount = amount * max_num;
		if (amount < 1) {
			target_amount = false;
		}
		if (target_amount) {
			calculated.innerHTML = "<strong class='campaign-contrib-amount'>Your campaign's total target amount will be $" + target_amount.toFixed(2) + "</strong>";
		} else {
			calculated.innerHTML = "";
		}
    },
    cancelEventPropagation: function(e) {
        if (!e) e = window.event;
        e.cancelBubble = true;
        if (e.stopPropagation) e.stopPropagation();
    }
}

var CampaignWizard = {
    init: function() {
        var input = document.getElementById('id_0-contribution_amount');
		if (input) {
			CampaignWizard.addCalculator(input);
			CampaignWizard.calculate();
		}
    },
    addCalculator: function(inp) {
        var calculator_span = document.createElement('div');
		calculator_span.setAttribute('id', 'campaignCalculator');
        inp.parentNode.insertBefore(calculator_span, inp.nextSibling);
        addEvent(inp, 'keyup', CampaignWizard.calculate);
		var max_num = document.getElementById('id_0-max_contributions');
		addEvent(max_num, 'keyup', CampaignWizard.calculate);
    },
    calculate: function() {
		var calculated = document.getElementById('campaignCalculator');
        var amount = document.getElementById('id_0-contribution_amount').value;
        var max_num = document.getElementById('id_0-max_contributions').value;
		var target_amount = amount * max_num;
		if (amount < 1) {
			target_amount = false;
		}
		if (target_amount) {
			calculated.innerHTML = "<strong class='campaign-contrib-amount'>Your campaign's total target amount will be $" + target_amount.toFixed(2) + "</strong>";
		} else {
			calculated.innerHTML = "";
		}
    },
    cancelEventPropagation: function(e) {
        if (!e) e = window.event;
        e.cancelBubble = true;
        if (e.stopPropagation) e.stopPropagation();
    }
}

addEvent(window, 'load', Campaign.init);
addEvent(window, 'load', CampaignWizard.init);

