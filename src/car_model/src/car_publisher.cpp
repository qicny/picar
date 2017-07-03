#include <string>
#include <cmath>
#include <chrono>
#include <thread>
#include <ros/ros.h>
#include <sensor_msgs/JointState.h>
#include <geometry_msgs/Twist.h>
#include <tf/transform_broadcaster.h>
#include <nav_msgs/Odometry.h>




class CarPublisher
{

        public:

                CarPublisher();
                ~CarPublisher();
                void initialize_joint_states(sensor_msgs::JointState* joint_state);
                void initialize_transformation(geometry_msgs::TransformStamped* trans, nav_msgs::Odometry* odom);
                void receive_Twist(const geometry_msgs::Twist msg);
                static void default_publish(CarPublisher* car_pub);

                sensor_msgs::JointState* joint_state;
                nav_msgs::Odometry* odom;
                geometry_msgs::TransformStamped* trans;

                ros::NodeHandle node;
                ros::Publisher joint_pub;
                ros::Publisher odom_pub;
                ros::Subscriber get_twist;
                ros::Time current_time, last_time;
                tf::TransformBroadcaster broadcaster;

                double f_left, f_right, back_wheels;
                double original_speed, turn, angle;
                double move_x, move_y, move_z, vx, vy, vth;
                bool first_message, turn_left, turn_right;

};




CarPublisher::CarPublisher()
{

        joint_pub = node.advertise<sensor_msgs::JointState>("joint_states", 50);
        odom_pub = node.advertise<nav_msgs::Odometry>("odom", 50);
        get_twist = node.subscribe("/cmd_vel", 1, &CarPublisher::receive_Twist, this);

        this->f_left = 0; this->f_right = 0; this->back_wheels = 0;
        this->original_speed = 0; this->turn = 1; this->angle = (M_PI/2);
        this->first_message = false; this->turn_left = false; this->turn_right = false;
        this->move_x = 0; this->move_y = 0; this->move_z = 0;
        this->vx = 0.5; this->vy = -0.5; this->vth = this->angle;
        this->current_time = ros::Time::now(); this->last_time = ros::Time::now();

        this->joint_state = new sensor_msgs::JointState();
        initialize_joint_states(joint_state);

        this->trans = new geometry_msgs::TransformStamped();
        this->odom = new nav_msgs::Odometry();
        initialize_transformation(trans, odom);

}



CarPublisher::~CarPublisher()
{
        delete this->joint_state;
        delete this->odom;
        delete this->trans;
}



void CarPublisher::initialize_joint_states(sensor_msgs::JointState* joint_state)
{

        joint_state->header.frame_id = "base_footprint";
        joint_state->header.stamp = ros::Time::now();
        joint_state->name.resize(7);
        joint_state->position.resize(7);
        std::string names[7] = { "base_footprint_joint" , "front_axle_to_base" , "back_axle_to_base" ,
        "front_left_wheel_to_front_axle" , "front_right_wheel_to_front_axle" ,
        "back_left_wheel_to_back_axle" , "back_right_wheel_to_back_axle" };

        for( int i = 0 ; i < 7 ; i++ )
        {
                joint_state->name[i] = names[i];
                joint_state->position[i] = 0;
        }

}


void CarPublisher::initialize_transformation(geometry_msgs::TransformStamped* trans, nav_msgs::Odometry* odom)
{

        trans->header.frame_id = "odom";
        trans->child_frame_id = "base_footprint";
        trans->header.stamp = ros::Time::now();
        trans->transform.translation.x = 0;
        trans->transform.translation.y = 0;
        trans->transform.translation.z = 0;
        trans->transform.rotation = tf::createQuaternionMsgFromYaw(0);

        odom->header.frame_id = "odom";
        odom->child_frame_id = "base_footprint";
        odom->header.stamp = ros::Time::now();
        odom->pose.pose.position.x = 0;
        odom->pose.pose.position.y = 0;
        odom->pose.pose.position.z = 0;
        odom->pose.pose.orientation = tf::createQuaternionMsgFromYaw((M_PI/2));
        odom->twist.twist.linear.x = 0;
        odom->twist.twist.linear.y = 0;
        odom->twist.twist.linear.z = 0;
        odom->twist.twist.angular.x = 0;
        odom->twist.twist.angular.y = 0;
        odom->twist.twist.angular.z = 0;

}


void CarPublisher::receive_Twist(const geometry_msgs::Twist msg)
{

        this->first_message = true;
        this->last_time = current_time;
        this->current_time = ros::Time::now();

        if( std::abs(msg.linear.x) != std::abs(vx) )
        {
                vx = msg.linear.x; vy = -vx;
        }

        if( std::abs(msg.angular.z) != std::abs(vth) ) // else, only a change in angular speed has been detected
        {
                vth = msg.angular.z;
                turn = msg.angular.z / original_speed;
        }

        double previous_angle = angle;

        if( msg.linear.y == 0 )// move
        {

                if( msg.linear.x > 0 )// if forward
                {
                        if( msg.angular.z > 0 )// u
                        {
                                f_left = 0.785;
                                f_right = 0.393;
                                back_wheels += 3.14;
                                angle += (M_PI/72);
                        }

                        else if( msg.angular.z == 0 )// i
                        {
                                f_left = 0;
                                f_right = 0;
                                back_wheels += 3.14;
                        }

                        else // o
                        {
                                f_left = -0.393;
                                f_right = -0.785;
                                back_wheels += 3.14;
                                angle -= (M_PI/72);
                        }

                }

                else if( msg.linear.x == 0 )// if( rotate
                {
                        if( msg.angular.z > 0 )// j
                        {
                                f_left = 0.785;
                                f_right = 0.393;
                                angle += (M_PI/72);
                        }

                        else if( msg.angular.z == 0 )// k
                        {
                                f_left = 0;
                                f_right = 0;
                        }

                        else // l
                        {
                                f_left = -0.393;
                                f_right = -0.785;
                                angle -= (M_PI/72);
                        }
                }

                else // if( reverse
                {
                        if( msg.angular.z < 0 )// m
                        {
                                f_left = 0.785;
                                f_right = 0.393;
                                back_wheels -= 3.14;
                                angle -= (M_PI/72);
                        }

                        else if( msg.angular.z == 0 )// ,
                        {
                                f_left = 0;
                                f_right = 0;
                                back_wheels -= 3.14;
                        }

                        else // .
                        {
                                f_left = -0.393;
                                f_right = -0.785;
                                back_wheels -= 3.14;
                                angle += (M_PI/72);
                        }
                }

        }

        while(angle < 0)
        {
                angle += 2*M_PI;
        }
        while(angle >= 2*M_PI)
        {
                angle -= 2*M_PI;
        }

        int x_dir, y_dir;
        (previous_angle < angle) ? turn_left = true : turn_left = false; turn_right = !turn_left;
        if(angle == 0)
        {
                x_dir = 1; y_dir = 0; turn_left = false; turn_right = false;
        }
        else if(angle > 0 && angle < (M_PI/2))
        {
                x_dir = 1; y_dir = 1;
        }
        else if(angle == (M_PI/2))
        {
                x_dir = 0; y_dir = 1; turn_left = false; turn_right = false;
        }
        else if(angle > (M_PI/2) && angle < (M_PI))
        {
                x_dir = -1; y_dir = 1;
        }
        else if(angle == M_PI)
        {
                x_dir = -1; y_dir = 0; turn_left = false; turn_right = false;
        }
        else if(angle > (M_PI) && angle < (M_PI*1.5))
        {
                x_dir = -1; y_dir = -1;
        }
        else if(angle == (M_PI*1.5))
        {
                x_dir = 0; y_dir = -1; turn_left = false; turn_right = false;
        }
        else
        {
                x_dir = 1; y_dir = -1;
        }

        move_x += x_dir*msg.linear.x;
        move_y += y_dir*msg.linear.x;
        move_z += msg.linear.z;


        this->joint_state->position[0] = 0;
        this->joint_state->position[1] = 0;
        this->joint_state->position[2] = 0;
        this->joint_state->position[3] = f_left;
        this->joint_state->position[4] = f_right;
        this->joint_state->position[5] = back_wheels;
        this->joint_state->position[6] = back_wheels;

        this->joint_state->header.stamp = current_time;
        joint_pub.publish(*this->joint_state);


        // tutorial from http://wiki.ros.org/navigation/Tutorials/RobotSetup/Odom

        geometry_msgs::Quaternion quat = tf::createQuaternionMsgFromYaw(angle-(M_PI/2));

        trans->header.stamp = current_time;
        trans->header.frame_id = "odom";
        trans->child_frame_id = "base_footprint";

        trans->transform.translation.x = move_x;
        trans->transform.translation.y = move_y;
        trans->transform.translation.z = move_z;
        trans->transform.rotation = quat;

        broadcaster.sendTransform(*trans);

        //next, we'll publish the odometry message over ROS
        odom->header.stamp = current_time;
        odom->header.frame_id = "odom";
        odom->child_frame_id = "base_footprint";

        odom->pose.pose.position.x = move_x;
        odom->pose.pose.position.y = move_y;
        odom->pose.pose.position.z = move_z;
        odom->pose.pose.orientation = tf::createQuaternionMsgFromYaw(angle);

        odom->twist.twist.linear.x = msg.linear.x;
        odom->twist.twist.linear.y = msg.linear.y;
        odom->twist.twist.linear.z = msg.linear.z;
        odom->twist.twist.angular.z = msg.angular.z;

        //publish the message
        odom_pub.publish(*odom);
}


void CarPublisher::default_publish(CarPublisher* car_pub)
{


        /*double update_angle = 0;
        if(car_pub->first_message)
        {
                (car_pub->turn_left) ? update_angle = (M_PI/72) : update_angle = -(M_PI/72);
        }
        */

        for(;;)
        {
                if(car_pub->first_message) {break;}
                car_pub->last_time = car_pub->current_time;
                car_pub->current_time = ros::Time::now();

                car_pub->joint_state->header.stamp = ros::Time::now();
                car_pub->joint_pub.publish(*car_pub->joint_state);

                //car_pub->angle += update_angle;

                car_pub->trans->header.stamp = ros::Time::now();
                car_pub->broadcaster.sendTransform(*car_pub->trans);
                //car_pub->trans->transform.translation.x += car_pub->trans->transform.translation.x;
                //car_pub->trans->transform.translation.y += car_pub->trans->transform.translation.y;
                //car_pub->trans->transform.translation.z += car_pub->trans->transform.translation.z;
                //car_pub->trans->transform.rotation = tf::createQuaternionMsgFromYaw(car_pub->angle-(M_PI/2));

                std::this_thread::sleep_for(std::chrono::milliseconds(1000));
        }

}


int main(int argc, char** argv)
{

        ros::init(argc, argv, "car_publisher");
        CarPublisher* car_pub = new CarPublisher();


        std::thread thr(CarPublisher::default_publish, car_pub);
        //thr.join();

        if(car_pub->first_message)
        {
                thr.detach();
        }

        ros::spin();
        delete car_pub;

        return 0;

}
