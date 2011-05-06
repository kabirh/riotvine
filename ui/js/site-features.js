// default AJAX setup
$.ajaxSetup({
  cache: 'false'
});


$.fn.pause = function(duration) {
    $(this).animate({dummy:1}, duration);
    return this;
};


function do_messages() {
	var msg = $("#hdr_messages");
	msg.slideDown("fast");
	if ($(".alert", msg).length == 0) {
		msg.pause(5000).slideUp("slow");
	}
};


function do_datetime_widgets() {
	$(".date_field").datepicker({
		  showOn:'button',
		  buttonImage:media_url + 'ui/images/view_calendar_timeline.png',
		  buttonImageOnly:true,
		  showButtonPanel:false,
		  showOtherMonths:true
	});
	$(".time_field").timePicker({
	  startTime: "09:00", // Using string. Can take string or Date object.
	  endTime: "23:00", // Using Date object here.
	  show24Hours: false,
	  separator: ':',
	  step: 60
	});	
};

function do_event_date_picker() {
  $(".event-date").datepicker({
		  showOn:'button',
		  buttonText:'Jump&nbsp;to&nbsp;Date',
		  buttonImageOnly:false,
		  showButtonPanel:true,
		  showOtherMonths:true,
		  closeText:'Cancel',
		  minDate:0,
		  onSelect:function() {
		    $("form.jump-to-date").submit();
		  }
  });
};


function do_form_widgets() {
	do_datetime_widgets();
};


function do_twitter() {
  $("iframe").attr("allowTransparency", "true");
  var twf = $("#idTwitterForm");
  var button = $("#idPostToTwitter", twf);
  var mesg = $(".tw_message", twf);
  var txt = $("#id_twitter_status");
  var count = $('<p class="tw_counter">0</p>').insertAfter(txt);
  
  txt.click(function() {
	$(this).css({'height':'4.5em'});
  }); // textarea click
  
  var refresh_char_count = function() {
	var v = txt.val();
	if (v.length > 140) {
	  txt.val(v.substr(0, 140));
	}
	count.text((140 - txt.val().length) + '');
  };
  
  txt.keyup(function() {
	refresh_char_count();
  }).keyup(); // textarea click
  
  var show_message = function(m) {
	mesg.css({'color':'#f40', 'text-align':'center', 'padding':'.25em .125em',
			  'margin':'.25em 0', 'background':'#000', 'font-weight':'bold',
			  'border':'1px solid #444'});
	mesg.text(m).slideDown("slow").animate({opacity: 1.0}, 1500).slideUp("slow");
  }; // show_message
  
  var before_send = function(xhr) {
	button.attr("disabled", "disabled").val("Posting...");
  };
  
  var complete = function(xhr, status) {
	button.removeAttr("disabled").val("Post to Twitter");
  };
  
  var success_fn = function(json) {
	var m;
	if (json) {
	  m = json.message;
	} else {
	  m = 'Status could not be posted';
	}
	show_message(m);
  }; // successFn
  
  var error_fn = function() {
	var m = 'Status could not be posted';
	show_message(m);
  }; // errorFn
  
  twf.submit(function() {
	  var options = {
		  dataType: "json",
		  beforeSend: before_send,
		  error: error_fn,
		  success: success_fn,
		  complete: complete
	  }; // options
	  $(this).ajaxSubmit(options); // ajaxSubmit
	  return false;
  }); // submit
}; // do_twitter


function do_photos() {
	$("#id-static-paginator").remove();
	$(".next-photo-link").show();
	var inp_del_photo = $("#id-delete-photo");
	var wrap = $("#id-image-wrapper");
	var before_send = function(xhr) {
		wrap.hide();
	}; // before_send
	var complete = function(xhr, status) {
		$(".next-photo-link").show();
		$("img", wrap).load(function() {
			wrap.fadeIn();
		});
	}; // complete
	var success_fn = function(json) {
		if (json) {
			photo_next_page = json.photo_next_page;
			if (inp_del_photo) {
				inp_del_photo.attr("value", json.photo_pk);
			} // inp_del_photo
			wrap.html(json.photo_html);
		} else {
			document.location.reload();
		}
	}; // successFn
	var error_fn = function() {
		document.location.reload();
	}; // errorFn	
	wrap.click(function(ev) {
		ev.preventDefault();
		var options = {
		  url: photo_view_url + photo_next_page,
		  dataType: "json",
		  beforeSend: before_send,
		  error: error_fn,
		  success: success_fn,
		  complete: complete
		}; // options
		$.ajax(options); // ajax call
		return false;
	}); // wrap.click
}; // do_photos


do_view_hide = function() {
	$(".view-hide-cue a").toggle(
		function() {
			$(this).parent(".view-hide-cue").next(".hidden-content").slideDown();
			$("span", $(this)).text("Hide");
			return false;
		}, // show
		function() {
			$(this).parent(".view-hide-cue").next(".hidden-content").slideUp();
			$("span", $(this)).text("View");
			return false;
		} // hide
	);
}; // do_view_hide


function fb_share_event_popup() {
  if (!IS_FB_SESSION) return;
  if (share_dialog_shown) return;
  var href = $("a.fb_share_btn");
  if (href.length > 0) {
    href = href.attr("href");
    share_dialog_shown = true;
    window.open(href, 'popupwindow', 'width=640,height=400,scrollbars=0,resizable=1,menubar=1,location=yes');
  }
} // fb_share_event


var fb_share_event = fb_share_event_popup;

function fb_share_event_fbml() {
  if (!IS_FB_SESSION) return;
  if (share_dialog_shown) return;
  href = full_share_url;
  share_dialog_shown = true;
  FB.Connect.showShareDialog(href, function() {});
} // fb_share_event


function do_calendar_add_remove_actions() {
    var cal_cta = $(".cal_add_cta").unbind("click");
    if (cal_cta.length > 0) {
      cal_cta.click(function() {
        var href = $(this).attr("href");
        if (href != '#') {
	        $(this).attr('href', '#');
	        $(".main_add_action").click();
        }
        return false;
      });
    }
	var lnk = $(".add_to_calendar,.remove_from_calendar");
	var city_events = false;
	if ($(".city-event").length > 0) {
	    city_events = true;
	}
	var share_btns = $(".event-page-share-btns");
	lnk.unbind("click");
	lnk.click(function() {
		var clnk = $(this);
		var url = clnk.attr("href");
		var do_slideout = clnk.hasClass('slideaction');
		// POST to this URL
		$.ajax({
				type: "POST",
				url: url,
				data: {},
				dataType: "json",
				success: function(data) {
					  if (data && data.success) {
						  var rlink = data.reverse_link;
						  var oldlink = data.old_link
						  // clnk.hide();
						  $('span.cal_mesg').remove();
						  // var msg = $("<span class='cal_mesg'>" + data.message + "</span>").insertAfter(clnk).hide();
						  var msg = $("<span class='cal_mesg'></span>").insertAfter(clnk).hide();
						  
						  var switchfn = function() {
							  if (data.link_type == "remove") {
								// broadcast to all copies of this event
								$(".track-event-copy").remove();
								var lnks = $(".add_to_calendar[href=\'" + oldlink + "\']");
								lnks.each(function() {
									var c = $(this);
									if (!c.hasClass("calendarlink") && !c.hasClass("calendarlink2")) {
										return;
									}
									c.removeClass('add_to_calendar');
									c.removeClass('slideaction');
									c.addClass('remove_from_calendar');
									if (c.hasClass("calendarlink2")) {
										c.html("I'm Out");
									} else { 
										c.html("I'm Out");
									}
									c.attr('href', rlink);		
									if (city_events) {
									    $(".city-retweet", c.closest(".city-event")).fadeIn(3000);
									}
									if (share_btns.length > 0) {
									  share_btns.show();
									}
									cal_cta.attr('href', '#');
								}); // links.each
								// $(".count_in_out").text("Count Me Out:");
							  } else {
								// broadcast to all copies of this event
								var lnks = $(".remove_from_calendar[href=\'" + oldlink + "\']");
								lnks.each(function() {
									var c = $(this);
									if (!c.hasClass("calendarlink") && !c.hasClass("calendarlink2")) {
										return;
									}
									c.removeClass('remove_from_calendar');
									c.addClass('add_to_calendar');
									c.addClass('slideaction');
									if (c.hasClass("calendarlink2")) {
										c.html("I'm In!");
									} else {
										c.html("I'm In!");
									}
									c.attr('href', rlink);
								}); // links.each
								// $(".count_in_out").text("Count Me In:");
							  }
							  clnk.attr('href', rlink);
							  clnk.show();
  							  if (do_slideout) {
							      do_cal_slideout(clnk);
							  }							  
							  do_fetch_calendar();
							  do_recommended_events();
							  do_event_interested();
						  }; // switchfn
						  
						  clnk.hide();
						  // msg.show().pause(100).fadeOut('slow', switchfn);
						  switchfn();
						  
					  }; // endif
				} // fn
		});// ajax
		return false;
	}); // click
}; // do_calendar_add_remove_actions


function do_event_calendar() {
	show_add_remove_calendar();
	do_calendar_add_remove_actions();
	do_event_promote();
}; // do_event_calendar


function show_add_remove_calendar() {
  $(".add_to_calendar, .remove_from_calendar, .add_event, .remove_event").show();
};


function do_fetch_calendar() {
  var c_id = $("#id_calendar");
  var url = event_calendar_url;
  if ($("body#event_page").length > 0) {
	 url = url + "?event_id=" + event_id;
  }
  if (c_id.length > 0) {
	$.get(url, function(data) {
	  c_id.html(data);
	  do_event_calendar();
	}, "html"); // get
  }
};


function do_recommended_events() {
  var c_id = $("#id_recommended");
  if (c_id.length > 0) {
	$.get(recommended_events_url, function(data) {
	  c_id.html(data);
	  do_event_calendar();
	}, "html"); // get
  }
}; // do_recommended_events


function do_event_interested() {
  if ($("body#event_page").length == 0) {return;}
  var c_id = $("#id_interested");
  var url = event_interested_url;
  if (c_id.length > 0) {
	$.get(url, function(data) {
	  c_id.html(data);
	  FB.Facebook.init(FB_API_KEY, "/fb/xd-receiver/");
	}, "html"); // get
  }
}; // do_interested


function do_event_comments() {
  var c_id = $("#id_event_comments");
  var url = event_comments_url;
  if (c_id.length > 0) {
	$.get(url, function(data) {
	  c_id.html(data);
	  if (has_comment_form) {comment_reply_fn();}
	}, "html"); // get
  }
}; // do_event_comments


function comment_reply_fn() {
	var textarea = $(".comment_form textarea");
	$("a.comment_reply").click(function() {
		var username = $(".userlink", $(this).parent("span"));
		var replyname = '@' + username.text();
		textarea.text(replyname);			  
		textarea.focus();
		return true;
	}); // click
}; // comment_reply_fn


var popover_dlg_params = {
	bgiframe: true,
	autoOpen: false,
	width: 600,
	height: 'auto',
	modal: true,
	hide: 'blind',
	buttons: {
		Cancel: function() {
			$(this).dialog('close');
		}
	},
	close: function() {
	  $("#amzn_widget,embed,object").css("visibility", "visible");
	}
};


function do_popover() {
	var pop = $(".popover");
	if (pop.length > 0) {
		var close = $("a.close", pop);
		close.click(function () {
			pop.dialog('close');
		});
		pop.dialog(popover_dlg_params);
		pop.dialog('open');
	}
}; // do_popover


function do_sso() {
	var sso = $("a.sso_initiate");
	var dlg = $("#id_sso_dialog");
	if (dlg.length > 0) {
		var close = $("a.close", dlg);
		close.click(function () {
			dlg.dialog('close');
		});
		dlg.dialog(popover_dlg_params);
		sso.click(function() {
		    $("#amzn_widget,embed,object").css("visibility", "hidden");
			dlg.dialog('open');
			return false;
		});
	}
}; // do_sso


var event_promo_dlg_params = popover_dlg_params;

function do_event_promote() {
	var dlg = $("#id_owner_promote_dialog");
	var act = $(".promote_dlg_opener");
	if (dlg.length > 0) {
		dlg.dialog(event_promo_dlg_params);
		if (typeof is_owner_first_visit == "boolean") {
			if (is_owner_first_visit) {
			    // $(".embed-code").attr("value", embed_code);
				$("#amzn_widget,embed,object").css("visibility", "hidden");
				dlg.dialog('open');
				is_owner_first_visit = false;
			}
		}
		act.unbind("click");
		act.click(function() {
		  $("#amzn_widget,embed,object").css("visibility", "hidden");
		  // $(".embed-code").attr("value", embed_code);
		  dlg.dialog('open');
		  return false;
		}); // act.click
	}
}; // do_sso


function do_cal_slideout(slideaction) {
	var con = slideaction.closest("span").next("div");
	if (!con.hasClass("slidebox-container")) {
	  con = con.next(".slidebox-container");
	}
	var box = $(".slidebox", con);
	if (box.hasClass('is-open')) {
        return;
	}
	
	/**
	var sh = $(".share-btns .share-btn", con);
	if (sh.length > 0) {
		sh.hide();
		$(".share-this").fadeIn();
	}
	**/
   
	var big = $(".share-btns-big").hide();
	box.pause(500).slideDown(750, function() {
		big.fadeIn();
		box.animate({backgroundColor:'#ffffff'}, 2000);
	});
	box.addClass("is-open");
}; // do_cal_slideout


function do_cal_closer() {
	var closer = $(".close-link");
	closer.unbind("click");
	closer.click(function() {
		var box = $(this).closest(".slidebox");
		var con = box.closest(".slidebox-container");
		box.slideUp("fast", function() {
		  box.css({backgroundColor:'#ffff99'});
		  var sh = $(".share-btns .share-btn", con);
		  if (sh.length > 0) {
			   $(".share-this").hide();
			   sh.fadeIn()
		  }
		});
		box.removeClass("is-open");
		return false;
	}); // closer.click
}; // do_cal_closer


var login_dlg_params = popover_dlg_params;

function do_global_login() {
    $("a.login_dialog").closest(".sso").show();
	var loginlinks = $("a.login_dialog");
	var dlg = $("#global_login_dlg");
	loginlinks.click(function() {
		if ($(this).hasClass("add_to_calendar")) {
		  var event_id = $(this).attr("href");
		  $.cookie("addevent", null, {path: '/', domain: COOKIE_DOMAIN});
		  $.cookie("addevent", event_id, {path: '/', domain: COOKIE_DOMAIN});
		} else {
		  $.cookie("addevent", null, {path: '/', domain: COOKIE_DOMAIN});
		};
		if ($(this).hasClass("gwo_goal")) {
		  doGoalDyn();
		};
		location.href = SIGNIN_LINK;
		return false;
		if (dlg.length > 0) {
			dlg.dialog(login_dlg_params);
			$("#amzn_widget,embed,object").css("visibility", "hidden");
			dlg.dialog('open');
			if ($(this).hasClass("gwo_goal")) {
			  doGoalDyn();
			}
		};
		return false;
	}); // loginlinks.click
    if (dlg.length > 0) {
		if (dlg.hasClass("show_login")) {
		  dlg.dialog(login_dlg_params);
		  $("#amzn_widget,embed,object").css("visibility", "hidden");
		  dlg.dialog('open');
		}
	};
}; // do_global_login


function city_event_hover() {
    return;
	var ex = $(".city-event");
	ex.hover(
		function() {
			$(".event-options", $(this)).show();
		},
		function() {
			$(".event-options", $(this)).hide();
		}
	); // hover
}; // city_event_hover


function do_embed_code() {
  $(".embed-code").keydown(function() {
    return false;
  });
  $(".embed-code").keyup(function() {
    return false;
  });
  $(".embed-code").click(function() {
    $(this).select();
  });
  $(".embed-code").bind("contextmenu", function() {
    $(this).select();
    return true;
  });
}; // do_embed_code
