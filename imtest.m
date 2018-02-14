close all;
clear all;
%%

rgb = RaspiImage('147.32.86.182', 1150);
r = rgb(:,:,1);
g = rgb(:,:,2);
b = rgb(:,:,3);

hsv = rgb2hsv(rgb);
hsv(:,:,1) = hsv(:,:,1)*360;
h = hsv(:,:,1);
s = hsv(:,:,2);
v = hsv(:,:,3);

imshow(rgb);
%%
figure(1)
clf()
subplot(1,2,1);
imshow(rgb)

figure(1)
subplot(1,2,1);
tol = 0.9;
%while 0
    figure(1);
    p = round(ginput(1));
    sel_rgb = squeeze(rgb(p(2), p(1), :))';
    sel_hsv = squeeze(hsv(p(2), p(1), :))';

    figure(2);
    rectangle('Position',[0,0,1,1],'FaceColor',sel_rgb)
    disp(sel_rgb)
    disp(sel_hsv)
%end
%%
kulicky = ((r+g+b)>150);
tst = (kulicky & ((0 < h) & (h < 20))); % Oran�ov�
figure(1);
subplot(1,2,2);
imshow(tst)


