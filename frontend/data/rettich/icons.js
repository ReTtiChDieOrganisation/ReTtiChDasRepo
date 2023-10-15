// rettich icons consist of a profile picture and a frame. The frame consists of a .png and a corresponding polyline color
var rettich_profile_pictures = {
    flo :
    {
        picture : "./frontend/icons/profile_pictures/flo.png",
        size_x : 33, // 3:4 ratio
	    size_y : 44, // 3:4 ratio
        anchor_x : 33/2, // picture_size_x/2
	    anchor_y : 44+22 // picture_size_y + adjust (adjust to center picture in frame)
    },
    // TODO: add pictures.
    felix :
    {
        picture : "./frontend/icons/profile_pictures/felix.png",
        size_x : 33, // 3:4 ratio
	    size_y : 44, // 3:4 ratio
        anchor_x : 33/2, // picture_size_x/2
	    anchor_y : 44+22 // picture_size_y + adjust (adjust to center picture in frame)
    },
    philipp :
    {
        picture : "./frontend/icons/profile_pictures/philipp.png",
        size_x : 33, // 3:4 ratio
	    size_y : 44, // 3:4 ratio
        anchor_x : 33/2, // picture_size_x/2
	    anchor_y : 44+22 // picture_size_y + adjust (adjust to center picture in frame)
    },
    default :
    {
        picture : "./frontend/icons/profile_pictures/default.png",
        size_x : 33, // 3:4 ratio
	    size_y : 44, // 3:4 ratio
        anchor_x : 33/2, // picture_size_x/2
	    anchor_y : 44+22 // picture_size_y + adjust (adjust to center picture in frame)
    }
};

var rettich_frames = {
    blue :
    {
        frame_fg : "./frontend/icons/frames/fg_blue.png",
        frame_bg : "./frontend/icons/frames/bg_white.png",
        line_color : "rgba("+0+" ,"+56+","+123+")",
        size_x : 54, // 3:4 ratio
        size_y : 72, // 3:4 ratio
        anchor_x : 54/2, // frame_size_x/2
        anchor_y : 72 // frame_size_y
    },
    green :
    {
        frame_fg : "./frontend/icons/frames/fg_green.png",
        frame_bg : "./frontend/icons/frames/bg_white.png",
        line_color : "rgba("+6+" ,"+80+","+0+")",
        size_x : 54, // 3:4 ratio
        size_y : 72, // 3:4 ratio
        anchor_x : 54/2, // frame_size_x/2
        anchor_y : 72 // frame_size_y
    },
    navyblue :
    {
        frame_fg : "./frontend/icons/frames/fg_navyblue.png",
        frame_bg : "./frontend/icons/frames/bg_white.png",
        line_color : "rgba("+32+" ,"+56+","+100+")",
        size_x : 54, // 3:4 ratio
        size_y : 72, // 3:4 ratio
        anchor_x : 54/2, // frame_size_x/2
        anchor_y : 72 // frame_size_y
    },
    neutral :
    {
        frame_fg : "./frontend/icons/frames/fg_neutral.png",
        frame_bg : "./frontend/icons/frames/bg_white.png",
        line_color : "rgba("+208+" ,"+206+","+206+")",
        size_x : 54, // 3:4 ratio
        size_y : 72, // 3:4 ratio
        anchor_x : 54/2, // frame_size_x/2
        anchor_y : 72 // frame_size_y
    },
    pride_fg :
    {
        frame_fg : "./frontend/icons/frames/fg_pride.png",
        frame_bg : "./frontend/icons/frames/bg_white.png",
        line_color : "rgba("+208+" ,"+206+","+206+")",
        size_x : 54, // 3:4 ratio
        size_y : 72, // 3:4 ratio
        anchor_x : 54/2, // frame_size_x/2
        anchor_y : 72 // frame_size_y
    },
    pride_bg :
    {
        frame_fg : "./frontend/icons/frames/fg_neutral.png",
        frame_bg : "./frontend/icons/frames/bg_pride.png",
        line_color : "rgba("+208+" ,"+206+","+206+")",
        size_x : 54, // 3:4 ratio
        size_y : 72, // 3:4 ratio
        anchor_x : 54/2, // frame_size_x/2
        anchor_y : 72 // frame_size_y
    },
    purple :
    {
        frame_fg : "./frontend/icons/frames/fg_purple.png",
        frame_bg : "./frontend/icons/frames/bg_white.png",
        line_color : "rgba("+112+" ,"+48+","+160+")",
        size_x : 54, // 3:4 ratio
        size_y : 72, // 3:4 ratio
        anchor_x : 54/2, // frame_size_x/2
        anchor_y : 72 // frame_size_y
    },
    red :
    {
        frame_fg : "./frontend/icons/frames/fg_red.png",
        frame_bg : "./frontend/icons/frames/bg_white.png",
        line_color : "rgba("+139+" ,"+0+","+0+")",
        size_x : 54, // 3:4 ratio
        size_y : 72, // 3:4 ratio
        anchor_x : 54/2, // frame_size_x/2
        anchor_y : 72 // frame_size_y
    },
    ukraine :
    {
        frame_fg : "./frontend/icons/frames/fg_ukraine.png",
        frame_bg : "./frontend/icons/frames/bg_white.png",
        line_color : "rgba("+255+" ,"+238+","+21+")",
        size_x : 54, // 3:4 ratio
        size_y : 72, // 3:4 ratio
        anchor_x : 54/2, // frame_size_x/2
        anchor_y : 72 // frame_size_y
    },
    yellow :
    {
        frame_fg : "./frontend/icons/frames/fg_yellow.png",
        frame_bg : "./frontend/icons/frames/bg_white.png",
        line_color : "rgba("+255+" ,"+238+","+21+")",
        size_x : 54, // 3:4 ratio
        size_y : 72, // 3:4 ratio
        anchor_x : 54/2, // frame_size_x/2
        anchor_y : 72 // frame_size_y
    },
    default :
    {
        frame_fg : "./frontend/icons/frames/fg_neutral.png",
        frame_bg : "./frontend/icons/frames/bg_white.png",
        line_color : "rgba("+0+" ,"+0+","+0+")",
        size_x : 54, // 3:4 ratio
        size_y : 72, // 3:4 ratio
        anchor_x : 54/2, // frame_size_x/2
        anchor_y : 72 // frame_size_y
    },
    /* TODO: 
     * black
     * white
     * bronce
     * silver
     * gold
     */
};
