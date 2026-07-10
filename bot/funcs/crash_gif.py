from moviepy.editor import *



def crop_video(input_path, output_path, target_second):
    clip = VideoFileClip(input_path)
    clip = clip.subclip(0, target_second)
    clip.write_videofile(output_path)

x = 10.5
x_per_s = 0.3536363636363636
input_video = "input.mp4"
output_video = "output.mp4"
target_second = x*x_per_s
print(target_second)
crop_video(input_video, output_video, target_second)
