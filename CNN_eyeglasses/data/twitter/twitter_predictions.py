import PIL.ImageOps
from PIL import Image
from sklearn import preprocessing
import numpy as np
import tensorflow as tf
import random
import os
import matplotlib.pyplot as plt

def new_weights(shape):
	return tf.Variable(tf.truncated_normal(shape, stddev=0.05))

def new_conv_layer(input,              # The previous layer.
                   num_input_channels, # Num. channels in prev. layer.
                   filter_size,        # Width and height of each filter.
                   num_filters):  # Use 2x2 max-pooling.

    # Shape of the filter-weights for the convolution.
    # This format is determined by the TensorFlow API.
    shape = [filter_size, filter_size, num_input_channels, num_filters]

    # Create new weights aka. filters with the given shape.
    weights = new_weights(shape=shape)

    # Create the TensorFlow operation for convolution.
    # Note the strides are set to 1 in all dimensions.
    # The first and last stride must always be 1,
    # because the first is for the image-number and
    # the last is for the input-channel.
    # But e.g. strides=[1, 2, 2, 1] would mean that the filter
    # is moved 2 pixels across the x- and y-axis of the image.
    # The padding is set to 'SAME' which means the input image
    # is padded with zeroes so the size of the output is the same.
    layer = tf.nn.conv2d(input=input,
                         filter=weights,
                         strides=[1, 1, 1, 1],
                         padding='SAME')

    # Add the biases to the results of the convolution.
    # A bias-value is added to each filter-channel.
    #layer += biases

    # Rectified Linear Unit (ReLU).
    # It calculates max(x, 0) for each input pixel x.
    # This adds some non-linearity to the formula and allows us
    # to learn more complicated functions.
    layer = tf.nn.relu(layer)

    # Note that ReLU is normally executed before the pooling,
    # but since relu(max_pool(x)) == max_pool(relu(x)) we can
    # save 75% of the relu-operations by max-pooling first.

    # We return both the resulting layer and the filter-weights
    # because we will plot the weights later.
    return layer, weights


def cnn_model(features, labels, mode):

	global dropOut
	global layer1Nodes
	global layer2Nodes
	# Input Layer
	# Celeb images are 28x28 pixels, and have one color channel
	# Reshape X to 4-D tensor: [batch_size, width, height, channels]
	input_layer = tf.reshape(features["x"], [-1, dim, dim, 1])
	print input_layer.shape
	# Convolutional Layer #1
	# Computes 32 features using a 5x5 filter with ReLU activation.
	# Padding is added to preserve width and height.
	# Input Tensor Shape: [batch_size, 28, 28, 1]
	# Output Tensor Shape: [batch_size, 28, 28, 32]
	#conv1 = new_conv_layer(input_layer, layer1Nodes, [5,5], tf.nn.relu)
	conv1, weights_conv1 = new_conv_layer(input=input_layer,num_input_channels=1,filter_size=5,num_filters=layer1Nodes)
	print conv1.shape
	
	# Pooling Layer #1
	# First max pooling layer with a 2x2 filter and stride of 2
	# Input Tensor Shape: [batch_size, 28, 28, 32]
	# Output Tensor Shape: [batch_size, 14, 14, 32]
	pool1 = tf.layers.max_pooling2d(inputs=conv1, pool_size=[2, 2], strides=2)
	print pool1.shape
	
	# Convolutional Layer #2
	# Computes 64 features using a 5x5 filter.
	# Padding is added to preserve width and height.
	# Input Tensor Shape: [batch_size, 14, 14, 32]
	# Output Tensor Shape: [batch_size, 14, 14, 64]
	#conv2 = new_conv_layer(pool1, layer2Nodes, [5,5], tf.nn.relu)
	conv2, weights_conv2 = new_conv_layer(input=pool1,num_input_channels=layer1Nodes,filter_size=5,num_filters=layer2Nodes)
	print conv2.shape
	
	# Pooling Layer #2
	# Second max pooling layer with a 2x2 filter and stride of 2
	# Input Tensor Shape: [batch_size, 14, 14, 64]
	# Output Tensor Shape: [batch_size, 7, 7, 64]
	pool2 = tf.layers.max_pooling2d(inputs=conv2, pool_size=[2, 2], strides=2)
	print pool2.shape
	
	# Flatten tensor into a batch of vectors
	# Input Tensor Shape: [batch_size, 7, 7, 64]
	# Output Tensor Shape: [batch_size, 7 * 7 * 64]
	pool2_flat = tf.reshape(pool2, [-1, 7 * 7 * layer2Nodes])
	print pool2_flat.shape
	# Dense Layer
	# Densely connected layer with 1024 neurons
	# Input Tensor Shape: [batch_size, 7 * 7 * 64]
	# Output Tensor Shape: [batch_size, 1024]
	dense = tf.layers.dense(inputs=pool2_flat, units=1024, activation=tf.nn.relu)
	print dense.shape
	# Add dropout operation; 0.4 probability that element will be kept
	dropout = tf.layers.dropout(
	    inputs=dense, rate=dropOut, training=mode == tf.estimator.ModeKeys.TRAIN)
	
	# Logits layer
	# Input Tensor Shape: [batch_size, 1024]
	# Output Tensor Shape: [batch_size, 2]
	logits = tf.layers.dense(inputs=dropout, units=2)
	print logits.shape
	predictions = {
	    # Generate predictions (for PREDICT and EVAL mode)
	    "classes": tf.argmax(input=logits, axis=1),
	    # Add `softmax_tensor` to the graph. It is used for PREDICT and by the
	    # `logging_hook`.
	    "probabilities": tf.nn.softmax(logits, name="softmax_tensor")
	}
	
	if mode == tf.estimator.ModeKeys.PREDICT:
	    return tf.estimator.EstimatorSpec(mode=mode, predictions=predictions)
	
	
	# Calculate Loss (for both TRAIN and EVAL modes)
	onehot_labels = tf.one_hot(indices=tf.cast(labels, tf.int32), depth=2)
	loss = tf.losses.softmax_cross_entropy(
	    onehot_labels=onehot_labels, logits=logits)
	# Configure the Training Op (for TRAIN mode)
	if mode == tf.estimator.ModeKeys.TRAIN:
	  optimizer = tf.train.AdamOptimizer(learning_rate=0.001)
	  train_op = optimizer.minimize(
	      loss=loss,
	      global_step=tf.train.get_global_step())
	  return tf.estimator.EstimatorSpec(mode=mode, loss=loss, train_op=train_op)
	# Add evaluation metrics (for EVAL mode)
	eval_metric_ops = {
	    "accuracy": tf.metrics.accuracy(
	        labels=labels, predictions=predictions["classes"])}
	return tf.estimator.EstimatorSpec(mode=mode, loss=loss, eval_metric_ops=eval_metric_ops)


def prediction_plot(predictions):
	'''
	this function takes the predictions from the twitter profile pictures and outputs a plot displaying the twitter profile pictures, 
	the probabilities that the profile picture contains eyeglasses (1) and no eyeglasses (0), and the actual prediction result
	'''
	for j,image_name in enumerate(os.listdir(DIR + 'profile_pics/aligned/')):
		prediction = predictions[j]
		predicted_class = prediction_dict[prediction['classes']]
		p_0 = prediction['probabilities'][0]
		p_1 = prediction['probabilities'][1]
		txt = 'P(Eyeglasses) = %.3f, P(No Eyeglasses) = %.3f' % (p_1, p_0)
		img = Image.open(DIR + 'profile_pics/aligned/' + image_name)
		fig = plt.figure()
		plt.imshow(img)
		plt.axis('off')
		plt.title('Predicted class: %s' % predicted_class)
		fig.text(.5, .05, txt, ha='center')
		plt.savefig('/Users/rvg/Documents/springboard_ds/springboard_portfolio/CNN_eyeglasses/data/twitter/profile_pics/predictions/%s_prediction.png'%image_name, dpi=350)
		plt.show()
		raw_input('...')
		plt.close()

prediction_dict = {0: 'No Eyeglasses (0)', 1: 'Eyeglasses (1)'}

DIR = '/Users/rvg/Documents/springboard_ds/springboard_portfolio/CNN_eyeglasses/data/twitter/'
dim = 28
n_images = len(os.listdir(DIR + 'profile_pics/aligned/'))

data = np.load(DIR + "twitter_test_imgs.npz")
twitter_images_labels = data['labels']
twitter_images = data['imageData']
twitter_imageNames = data['imageNames']

#flattening the input array and reshaping the labels as per requirement of the tnesorflow algo
twitter_images = twitter_images.reshape([n_images,dim**2])
twitter_images_labels = twitter_images_labels.reshape([n_images,])

#standardizing the image data set with zero mean and unit standard deviation
twitter_images = preprocessing.scale(twitter_images)
twitter_data = np.asarray(twitter_images, dtype=np.float32)  # Returns np.array
twitter_labels = twitter_images_labels

global dropOut
global layer1Nodes
global layer2Nodes
dropOut = 0.4
layer1Nodes = 32
layer2Nodes = 64
modelName = "/Users/rvg/Documents/springboard_ds/springboard_portfolio/CNN_eyeglasses/modeling/celeb_convnet_model_aligned"+str(dropOut)+str(layer1Nodes)+str(layer2Nodes)

celeb_classifier = tf.estimator.Estimator(
  model_fn=cnn_model, model_dir=modelName)

# Evaluate on twitter images
twitter_input_fn = tf.estimator.inputs.numpy_input_fn(
  x={"x": twitter_data},
  y=twitter_labels,
  num_epochs=1,
  shuffle=False)
twitter_results = celeb_classifier.evaluate(input_fn=twitter_input_fn)
print("Twitter accuracy" ,twitter_results)
twitter_predictions = list(celeb_classifier.predict(input_fn=twitter_input_fn))

prediction_plot(twitter_predictions)