// static/script.js
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const imageInput = document.getElementById('imageInput');

// Access the webcam
navigator.mediaDevices.getUserMedia({ video: true })
  .then(stream => {
    video.srcObject = stream;
  });

function capture() {
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
  canvas.toBlob(blob => {
    const file = new File([blob], 'capture.jpg', { type: 'image/jpeg' });

    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);

    // Create a new file input element
    const input = document.createElement('input');
    input.type = 'file';
    input.name = 'image';
    input.files = dataTransfer.files;

    // Append to form and submit
    document.getElementById('loginForm').appendChild(input);
    document.getElementById('loginForm').submit();
  }, 'image/jpeg');
}
