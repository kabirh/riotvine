/*
 * overLabel 0.1.7	http://jlix.net/extensions/jquery/overLabel/0.1.7
 * + forRef 0.1.5		http://jlix.net/extensions/jquery/forRef/0.1.5
 *
 * Copyright (c) 2009 Sander Aarts	(jlix.net)
 * Dual licensed under the MIT (http://jlix.net/MIT.txt)
 * and GPL (http://jlix.net/GPL.txt) licenses.
 *
 * Requires jQuery to work	(jquery.com). Tested with version 1.2.6
 *
 * 2008-10-03
 */
(function($) {
	$.fn.extend( {
		overLabel: function() { // v0.1.7
			//	Makes 'overLabel' behavior possible. Works both on labels and form fields.
			//	Concept based on http://www.alistapart.com/articles/makingcompactformsmoreaccessible/
			//	CSS:		.jsOverLabel (on label)
			//				.jsOverLabelBlur (on parent of form field: blur)
			//	Deps.:	forRef() method (v0.1+)
			return this
				.each( function() {
					var jThis = $(this);
					var jRef = jThis.forRef();
					if ( jThis.is("label[for]") ) {
						var jFormControl = jRef;
						var jLabels = jThis;
					} else {
						var jFormControl = jThis;
						var jLabels = jRef;
					}
					if ( !( jFormControl.length > 0 && jLabels.length > 0 ) ) return true;	// continue
					
					jLabels.each( function() {
						$(this).addClass("jsOverLabel");
						if ( jFormControl.val() === "" ) jFormControl.parent().addClass("jsOverLabelBlur");
						jFormControl
							.focus( function() { $(this).parent().removeClass("jsOverLabelBlur"); } )
							.blur( function() { 
								var jFormControl = $(this);
								if ( jFormControl.val() === "" ) jFormControl.parent().addClass("jsOverLabelBlur");
							} )
							.click( function() { 						// needed for Webkit to pass focus to input
								$(this).forRef().each( function() {	// .focus() does not seem to work on every matched element, therefore .each() 
									this.focus();
								} );
							} );
					} );
				} );
		},
		forRef: function() { // v0.1.5
			//	Finds corresponding label(s), input, select or textarea, based on for= attribute of first matched element. Works both ways.
			return this.is("label[for]") ? $("#" + this[0].htmlFor) : $("label[for='" + this[0].id + "']");
		}
	} );
} )(jQuery);