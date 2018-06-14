close all;
clear all;

%%
server = '147.32.86.182';
port = 1150;

%%
%obj = 'Detector-Red';
%obj = 'Detector-Green';
obj = 'Detector-Blue';
threshold = 120;

%dwnsample = webread(sprintf('http://%s:%d/%s/%s', server, port, obj, 'whole'));
dwnsample = RaspiImage(server, port, obj, 'downsample');
figure(1)
imagesc(dwnsample)
colorbar


%roi = webread(sprintf('http://%s:%d/%s/%s', server, port, obj, 'roi'));
roi = RaspiImage(server, port, obj, 'roi');
figure(2)
imagesc(roi)
colorbar

%%
% RGB image
figure(3)
rgb = RaspiImage(server, port, 'Processor', 'any');
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

rgb = RaspiImage(server, port, 'Detector-Green', 'image_dwn');
%rgb_dwn = rgb(1:16:end, 1:16:end,:);
imshow(rgb);
%%
figure(1)
clf()
subplot(1,2,1);
imshow(rgb)

figure(1)
subplot(1,2,1);
tol = 0.9;
while 1
    figure(1);
    p = round(ginput(1));
    sel_rgb = squeeze(rgb(p(2), p(1), :))';
    sel_hsv = squeeze(hsv(p(2), p(1), :))';

    figure(2);
    rectangle('Position',[0,0,1,1],'FaceColor',sel_rgb)
    disp(sel_rgb)
    disp(sel_hsv)
end
%%
kulicky = ((r+g+b)>150);
tst = (kulicky & ((0 < h) & (h < 20))); % Oran�ov�
figure(1);
subplot(1,2,2);
imshow(tst)


%%
r = RaspiImage(server, port, 'Detector-RedC', 'thrs');
g = RaspiImage(server, port, 'Detector-GreenC', 'thrs');
b = RaspiImage(server, port, 'Detector-BlueC', 'thrs');
rgb = cat(3, r, g, b);
%rgb_dwn = rgb(1:16:end, 1:16:end,:);
imshow(rgb);
drawnow
