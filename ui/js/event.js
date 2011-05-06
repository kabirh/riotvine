function venue_select(dlg) {
	// event handler for when a venue is selected
	var form = $("form#id_event_edit_form");
	var submit = $("input[type=''submit'']", form);
	var search_type = form.data("venue_search_type");
	form.data("venue_search_type", "explicit");	  
	var results = $(".result");
	results.hover(function() {$(this).addClass('over')}, function() {$(this).removeClass('over')});
	results.click(function() {
	  var vjson = $(".vjson", $(this)).text();
	  var source = $(".source", $(this)).text();
	  var title = $(".title", $(this)).text();
	  $("#id_venue_source").val(source);
	  $("#id_venue_params").val(vjson);
	  $("#id_venue_name").val(title);
	  venue_search_done = true;
	  $(".select_address").remove();
	  if (vjson) {
		  var js = eval("(" + vjson + ")");		  
		  var adrl =  js.addressLines.join(", ");
		  $("<div class='select_address'><strong>" + adrl + "</strong></div>").insertAfter($("#venue_search"));		  
	  };
	  dlg.fadeOut().dialog('close');
	  if (search_type == "implicit") {
	    submit.attr("value", "Please Wait...");
  	    submit.attr("disabled", "disabled");
	    form.submit();
	  }	  
	}); // result click
}

var venue_dlg_params = {
	bgiframe: true,
	autoOpen: false,
	width: 600,
	height: 480,
	modal: true,
	title: 'Select a venue',
	buttons: {
		Cancel: function() {
			$(this).dialog('close');
		}
	},
	close: function() {}
};

function venue_mgmt() {
	// insert search button
	var inp = $("input#id_venue_name");
	if (inp.length == 0) {
		return;
	}
	var btn = $("<button id='venue_search'>Search</button>").insertAfter(inp);
	var dlg = $("<div id='venue_dlg'></div>").insertAfter(btn);
	dlg.hide();
	
	var px = $("#id_venue_params");
	if (px.length > 0) {
	  var vjson = px.val();
	  if (vjson != '') {
		  var js = eval("(" + vjson + ")");
		  $(".select_address").remove();
		  var adrl = js.addressLines;
		  if (adrl == ', ,  ') {
		    adrl = '';
		  }
		  $("<div class='select_address'><strong>" + adrl + "</strong></div>").insertAfter($("#venue_search"));
	  }
	}
	
	// add search click function
	btn.click(function() {
		var val = inp.val();
		if (!val) {
			alert("Please enter something in the Venue Name field first.");
			return false;
		}
		$.ajax({
		   url: venue_search_url,
		   type: "POST",
		   data: {q: val},
		   dataType: "html",
		   error: function() {
		   }, // error
		   success: function(data) {
			   if (data) {
				   dlg.html(data);
				   venue_select(dlg);
				   dlg.dialog(venue_dlg_params);
				   dlg.show().dialog('open');
			   } // if success
		   } // success
		}); // .ajax
		return false;
	}); // btn.click
	
	inp.click(function() {
	  venue_search_done = false;
	});

	inp.keypress(function(e) {
	    venue_search_done = false;	    
		if(e.keyCode == 13) {
			btn.click();
			e.preventDefault();
		}
	}); // enter pressed in venue
	
	var form = $("form#id_event_edit_form");
	form.submit(function() {
	  	 if (!venue_search_done) {
	  	   form.data("venue_search_type", "implicit");	 
	  	   btn.click();
	  	   return false;
	  	 }
	}); // form.submit
}; // venue_mgmt


function do_bg_image() {
  var tw = $("#id_use_twitter_background");
  if (tw.length == 0) return;
  if (tw.is(':checked')) {
    $("#id_tr_bg_image").toggle();
  }
  tw.click(function() {
      $("#id_tr_bg_image").toggle();
      return true;
  });
  $("#id_event_edit_form").submit(function() {
    $("#id_tr_bg_image:hidden").remove();
    return true;
  });
}; // bg_image


