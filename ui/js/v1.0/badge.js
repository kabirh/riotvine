function rvbadge() {
	var ver="1.0";
	var xurl="";
	var event="";
	var w=227;
	var h=330;
	if (typeof rv_url == "string") {
		xurl=rv_url;
	} else {
		xurl='riotvine.com';
	}
	if (typeof rv_event == "string") {
		event=escape(rv_event);
	} else {
		return false;
	}
	var _url='http://' + xurl + '/event/badge/' + event + '/?v=' + ver;
	document.write('<iframe class="riotvine" style="width:227px;height:330px;" src="'+_url+'" height="'+h+'" width="'+w+'" frameborder="0" scrolling="no"></iframe>');
};
rvbadge();

