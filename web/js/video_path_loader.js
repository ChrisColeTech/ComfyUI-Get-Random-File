import { app } from "../../../scripts/app.js";

app.registerExtension({
    name: "Comfy.VideoPathPlayer",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "VideoPathLoader") {
            
            // Hook into the node creation execution
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                onNodeCreated?.apply(this, arguments);

                // Create HTML video player element
                const videoElement = document.createElement("video");
                videoElement.controls = true;
                videoElement.loop = true;
                videoElement.muted = true;
                videoElement.style.width = "100%";
                videoElement.style.marginTop = "10px";
                videoElement.style.borderRadius = "4px";

                // Bind the DOM element to the node interface
                this.addDOMWidget("video_preview", "video", videoElement, {
                    serialize: false,
                });

                // Set initial node layout sizing to accommodate video
                this.size = 0;
            };

            // Update the video element whenever the backend returns the executed path
            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (message) {
                onExecuted?.apply(this, arguments);
                
                // Read the string path output from the Python side
                const videoPath = message?.output?.video_path?.[0];
                const videoWidget = this.widgets?.find(w => w.name === "video_preview");

                if (videoPath && videoWidget?.element) {
                    // Modern browsers block local files via security policies.
                    // Converting local absolute path to ComfyUI asset route URL
                    videoWidget.element.src = `/view?filename=${encodeURIComponent(videoPath)}&type=absolute`;
                    videoWidget.element.load();
                }
            };
        }
    }
});
